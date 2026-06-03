"""
Prometheus metrics 集成测试 - Phase 5.7

设计：
- 默认 METRICS_ENABLED 未设置 → setup_metrics 返回 False，metrics 端点不挂载
- METRICS_ENABLED=true → setup_metrics 装中间件 + /metrics 端点
- 计数器 inc 后能从 /metrics 文本里读到
- record_llm_call / record_chat_stream_chunk 是 noop 当未启用
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tantan.backend.utils import metrics as metrics_module
from tantan.backend.utils.metrics import (
    is_metrics_configured,
    is_metrics_enabled,
    setup_metrics,
    record_llm_call,
    record_chat_stream_chunk,
    http_requests_total,
    llm_calls_total,
    chat_stream_chunks_total,
    app_info,
)


@pytest.fixture(autouse=True)
def _reset_metrics_module_state():
    """每个测试前后清空模块级 state，保证 setup_metrics 可重复装在各自 app 上"""
    metrics_module._metrics_initialized = False
    metrics_module._registry = None
    metrics_module.http_requests_total = None
    metrics_module.http_request_duration_seconds = None
    metrics_module.llm_calls_total = None
    metrics_module.chat_stream_chunks_total = None
    metrics_module.app_info = None
    yield
    metrics_module._metrics_initialized = False
    metrics_module._registry = None


class TestMetricsDisabled:
    """默认未启用"""

    def test_is_metrics_configured_default_false(self, monkeypatch):
        monkeypatch.delenv("METRICS_ENABLED", raising=False)
        assert is_metrics_configured() is False

    def test_setup_returns_false_when_disabled(self, monkeypatch):
        monkeypatch.delenv("METRICS_ENABLED", raising=False)
        app = FastAPI()
        assert setup_metrics(app) is False
        assert is_metrics_enabled() is False

    def test_hooks_are_noop_when_disabled(self, monkeypatch):
        monkeypatch.delenv("METRICS_ENABLED", raising=False)
        record_llm_call("test", "success")
        record_chat_stream_chunk("test")
        assert http_requests_total is None
        assert llm_calls_total is None
        assert chat_stream_chunks_total is None


class TestMetricsEnabled:
    """METRICS_ENABLED=true"""

    def test_is_metrics_configured_true(self, monkeypatch):
        for val in ("1", "true", "yes"):
            monkeypatch.setenv("METRICS_ENABLED", val)
            assert is_metrics_configured() is True

    def test_setup_creates_metrics(self, monkeypatch):
        monkeypatch.setenv("METRICS_ENABLED", "true")
        app = FastAPI()
        assert setup_metrics(app) is True
        assert is_metrics_enabled() is True
        assert metrics_module.http_requests_total is not None

    def test_setup_idempotent(self, monkeypatch):
        monkeypatch.setenv("METRICS_ENABLED", "true")
        app = FastAPI()
        setup_metrics(app)
        assert setup_metrics(app) is True

    def test_metrics_endpoint_exposes_text(self, monkeypatch):
        monkeypatch.setenv("METRICS_ENABLED", "true")
        app = FastAPI()
        setup_metrics(app)

        @app.get("/test")
        def test_route():
            return {"ok": True}

        with TestClient(app) as client:
            resp = client.get("/test")
            assert resp.status_code == 200

            metrics_resp = client.get("/metrics")
            assert metrics_resp.status_code == 200
            text = metrics_resp.text
            assert "tantan_http_requests_total" in text
            assert "tantan_app_info" in text
            assert "/test" in text

    def test_counter_increments(self, monkeypatch):
        monkeypatch.setenv("METRICS_ENABLED", "true")
        app = FastAPI()
        setup_metrics(app)

        @app.get("/api/ping")
        def ping():
            return {"pong": True}

        with TestClient(app) as client:
            client.get("/api/ping")
            client.get("/api/ping")
            client.get("/api/ping")

            text = client.get("/metrics").text
            assert 'tantan_http_requests_total{method="GET",path="/api/ping",status="200"} 3.0' in text

    def test_record_llm_call_increments(self, monkeypatch):
        monkeypatch.setenv("METRICS_ENABLED", "true")
        app = FastAPI()
        setup_metrics(app)
        record_llm_call("professional_question", "success")
        record_llm_call("professional_question", "success")
        record_llm_call("chitchat", "error")

        with TestClient(app) as client:
            text = client.get("/metrics").text
            assert 'tantan_llm_calls_total{intent="professional_question",status="success"} 2.0' in text
            assert 'tantan_llm_calls_total{intent="chitchat",status="error"} 1.0' in text

    def test_record_chat_stream_chunk_increments(self, monkeypatch):
        monkeypatch.setenv("METRICS_ENABLED", "true")
        app = FastAPI()
        setup_metrics(app)
        record_chat_stream_chunk("chitchat")
        record_chat_stream_chunk("chitchat")
        record_chat_stream_chunk("guidance")

        with TestClient(app) as client:
            text = client.get("/metrics").text
            assert 'tantan_chat_stream_chunks_total{intent="chitchat"} 2.0' in text
            assert 'tantan_chat_stream_chunks_total{intent="guidance"} 1.0' in text

    def test_duration_histogram_records(self, monkeypatch):
        monkeypatch.setenv("METRICS_ENABLED", "true")
        app = FastAPI()
        setup_metrics(app)

        @app.get("/api/slow")
        def slow():
            import time
            time.sleep(0.05)
            return {"slow": True}

        with TestClient(app) as client:
            client.get("/api/slow")
            text = client.get("/metrics").text
            assert "tantan_http_request_duration_seconds_bucket" in text
            assert "tantan_http_request_duration_seconds_count" in text
