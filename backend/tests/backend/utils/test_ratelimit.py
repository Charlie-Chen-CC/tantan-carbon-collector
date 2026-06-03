"""
速率限制集成测试 - Phase 5.8

设计：
- 默认 RATELIMIT_ENABLED=true → limiter 存在
- RATELIMIT_ENABLED=false → setup_ratelimit 不挂载
- limit_auth / limit_upload / limit_chat 装饰器在 limiter 存在时生效
- 触发限流：返回 429 + Retry-After 头
- 测试用足够小的 limit 触发节流（不依赖真实 200/min）
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tantan.backend.utils import ratelimit as rl_module
from tantan.backend.utils.ratelimit import (
    is_ratelimit_configured,
    is_ratelimit_enabled,
    setup_ratelimit,
    get_limiter,
    limit_auth,
    limit_upload,
    limit_chat,
    GLOBAL_DEFAULT,
    AUTH_DEFAULT,
    UPLOAD_DEFAULT,
    CHAT_DEFAULT,
)


@pytest.fixture(autouse=True)
def _reset_ratelimit_module_state():
    metrics_module = rl_module
    metrics_module._ratelimit_initialized = False
    yield
    metrics_module._ratelimit_initialized = False


class TestRateLimitConfig:
    """配置开关"""

    def test_default_enabled(self, monkeypatch):
        monkeypatch.delenv("RATELIMIT_ENABLED", raising=False)
        assert is_ratelimit_configured() is True

    def test_disabled_via_env(self, monkeypatch):
        for val in ("0", "false", "no"):
            monkeypatch.setenv("RATELIMIT_ENABLED", val)
            assert is_ratelimit_configured() is False

    def test_limiter_built_at_import(self):
        """Limiter 在模块 import 时就构造（不依赖 setup_ratelimit）"""
        limiter = get_limiter()
        assert limiter is not None


class TestRateLimitDecorators:
    """装饰器"""

    def test_limit_auth_returns_decorated_function(self):
        @limit_auth
        async def fake_endpoint(request: Request):
            return {"ok": True}

        assert callable(fake_endpoint)
        assert getattr(fake_endpoint, "__wrapped__", None) is not None

    def test_limit_upload_returns_decorated_function(self):
        @limit_upload
        async def fake_endpoint(request: Request):
            return {"ok": True}

        assert callable(fake_endpoint)

    def test_limit_chat_returns_decorated_function(self):
        @limit_chat
        async def fake_endpoint(request: Request):
            return {"ok": True}

        assert callable(fake_endpoint)


class TestRateLimitMiddleware:
    """slowapi 中间件 + 异常处理"""

    def test_setup_registers_middleware(self, monkeypatch):
        monkeypatch.setenv("RATELIMIT_ENABLED", "true")
        app = FastAPI()
        assert setup_ratelimit(app) is True
        assert is_ratelimit_enabled() is True

    def test_setup_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("RATELIMIT_ENABLED", "false")
        app = FastAPI()
        assert setup_ratelimit(app) is False
        assert is_ratelimit_enabled() is False

    def test_setup_idempotent(self, monkeypatch):
        monkeypatch.setenv("RATELIMIT_ENABLED", "true")
        app = FastAPI()
        setup_ratelimit(app)
        assert setup_ratelimit(app) is True


class TestRateLimitTriggers:
    """限流触发"""

    def test_auth_limit_triggers_429(self, monkeypatch):
        """AUTH_DEFAULT 5/min：连发 6 次登录应触发 429"""
        from fastapi.responses import JSONResponse
        from starlette.testclient import TestClient as TC

        monkeypatch.setenv("RATELIMIT_ENABLED", "true")
        app = FastAPI()
        setup_ratelimit(app)

        @app.post("/api/auth/login-test")
        @limit_auth
        async def login_test(request: Request, response: JSONResponse):
            return {"ok": True}

        with TC(app) as client:
            statuses = []
            for _ in range(6):
                r = client.post("/api/auth/login-test", json={"x": 1})
                statuses.append(r.status_code)
            assert statuses[:5] == [200] * 5
            assert statuses[5] == 429, f"实际状态序列: {statuses}"
            last = client.post("/api/auth/login-test", json={"x": 1})
            assert "Retry-After" in last.headers or "retry-after" in {k.lower() for k in last.headers}

    def test_global_default_applies_to_unlisted_routes(self, monkeypatch):
        """全局 200/min 不应被轻易触发；用 mock 限制来验证中间件工作"""
        from starlette.testclient import TestClient as TC

        monkeypatch.setenv("RATELIMIT_ENABLED", "true")
        app = FastAPI()
        setup_ratelimit(app)

        @app.get("/api/anything")
        def anything():
            return {"ok": True}

        with TC(app) as client:
            r = client.get("/api/anything")
            assert r.status_code == 200
            assert "X-RateLimit-Limit" in r.headers or "x-ratelimit-limit" in {k.lower() for k in r.headers}


class TestRateLimitDefaultConstants:
    """默认值常量稳定（外部脚本可能依赖）"""

    def test_global_default(self):
        assert GLOBAL_DEFAULT == "200/minute"

    def test_auth_default(self):
        assert AUTH_DEFAULT == "5/minute"

    def test_upload_default(self):
        assert UPLOAD_DEFAULT == "10/minute"

    def test_chat_default(self):
        assert CHAT_DEFAULT == "30/minute"
