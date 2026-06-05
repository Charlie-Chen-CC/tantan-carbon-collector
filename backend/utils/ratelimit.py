"""
速率限制 - 碳管师收资系统 (Phase 5.8 / S3)

设计：
- **默认启用**，关闭需设 `RATELIMIT_ENABLED=false`
- 使用 slowapi 内存 Limiter（单进程；多 worker 需切 Redis storage）
- 默认限制：
  - 全局：200/min per IP（`GLOBAL_DEFAULT`）
  - 登录/注册：5/min per IP（防爆破）
  - 文件上传：10/min per IP
- 触发限流：返回 429 + `Retry-After` 头
- 缺 slowapi 时 NoOp
- **Limiter 在模块 import 时就构造**（避免装饰器在 import 阶段拿不到 limiter）
"""
import os
import logging
from typing import Any, Optional, Callable

# 默认限流策略字符串
GLOBAL_DEFAULT = "200/minute"
AUTH_DEFAULT = "5/minute"
UPLOAD_DEFAULT = "10/minute"
CHAT_DEFAULT = "30/minute"

_ratelimit_initialized: bool = False
_limiter: Any = None


def _build_limiter() -> Optional[Any]:
    """构造 slowapi Limiter。缺包返回 None。"""
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
    except ImportError:
        return None
    return Limiter(
        key_func=get_remote_address,
        default_limits=[GLOBAL_DEFAULT],
        headers_enabled=True,
        strategy="fixed-window",
        # 跳过 .env 读取：项目用 pydantic Settings 统一管环境变量
        # slowapi 默认读 CWD 下 .env，starlette.config._read_file 用 open() 不指定 encoding
        # 在 Windows 默认 GBK 上会 UnicodeDecodeError（即使 .env 是 UTF-8）
        config_filename=None,
    )


# 模块 import 时立即构造（装饰器需要在 import 阶段拿到 limiter 实例）
_limiter = _build_limiter()


def is_ratelimit_configured() -> bool:
    """是否启用（默认 True）"""
    return os.getenv("RATELIMIT_ENABLED", "true").lower() not in ("0", "false", "no")


def is_ratelimit_enabled() -> bool:
    return _ratelimit_initialized


def get_limiter() -> Any:
    return _limiter


def setup_ratelimit(app: Any) -> bool:
    """挂载 slowapi Limiter + 异常处理器

    Args:
        app: FastAPI 应用

    Returns:
        True 表示已启用
    """
    global _ratelimit_initialized
    if _ratelimit_initialized:
        return True
    if not is_ratelimit_configured():
        return False
    if _limiter is None:
        logging.getLogger(__name__).warning(
            "RATELIMIT_ENABLED 但缺 slowapi；跳过限流初始化"
        )
        return False

    try:
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware
        from slowapi import _rate_limit_exceeded_handler
    except ImportError:
        logging.getLogger(__name__).warning("slowapi 模块导入失败；跳过限流")
        return False

    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    _ratelimit_initialized = True
    return True


def reset_limiter() -> None:
    """清空限流计数（测试用）

    slowapi Limiter 内置固定窗口的 storage（`MovingWindow` / 内存 storage），
    测试套件共享同一 IP（127.0.0.1）时连续注册/登录很快耗尽 5/min 上限。
    每个测试函数入口调一次 `reset_limiter()` 即可避免。
    """
    if _limiter is None:
        return
    try:
        _limiter.reset()
    except Exception:
        # storage 不可重置时（极端情况）静默兜底
        pass


def limit_auth(func: Callable) -> Callable:
    """装饰器：登录/注册 5/min per IP"""
    if _limiter is None:
        return func
    return _limiter.limit(AUTH_DEFAULT)(func)


def limit_upload(func: Callable) -> Callable:
    """装饰器：文件上传 10/min per IP"""
    if _limiter is None:
        return func
    return _limiter.limit(UPLOAD_DEFAULT)(func)


def limit_chat(func: Callable) -> Callable:
    """装饰器：聊天 30/min per IP"""
    if _limiter is None:
        return func
    return _limiter.limit(CHAT_DEFAULT)(func)
