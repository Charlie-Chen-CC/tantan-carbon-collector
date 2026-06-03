"""
Prometheus 指标 - 碳管师收资系统 (Phase 5.7)

设计：
- **默认关闭**（METRICS_ENABLED=true 才启用）
- 启用时暴露 `/metrics` 端点（Prometheus 抓取）
- 关键指标：
  - `http_requests_total{method,path,status}` - 计数器
  - `http_request_duration_seconds{method,path}` - 直方图
  - `llm_calls_total{intent,status}` - LLM 调用计数
  - `chat_stream_chunks_total{intent}` - SSE 流式 chunk 计数
  - `app_info{version,environment}` - Gauge（恒为 1，附元信息）
- 缺 prometheus_client 时 NoOp（不抛 import 错）
- **使用独立 CollectorRegistry**（避免重复加载时全局默认 registry 抛 Duplicated timeseries）
"""
import os
import time
from typing import Any, Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_metrics_initialized: bool = False
_registry: Any = None  # prometheus_client.CollectorRegistry 实例

# 模块级指标（缺包时为 None）
http_requests_total: Any = None
http_request_duration_seconds: Any = None
llm_calls_total: Any = None
chat_stream_chunks_total: Any = None
app_info: Any = None


def is_metrics_configured() -> bool:
    return os.getenv("METRICS_ENABLED", "").lower() in ("1", "true", "yes")


def is_metrics_enabled() -> bool:
    return _metrics_initialized


def get_registry() -> Any:
    """返回当前 registry（未启用时为 None）"""
    return _registry


def _build_metrics() -> bool:
    """构造 prometheus_client 指标对象到独立 registry。缺包返回 False。"""
    global http_requests_total, http_request_duration_seconds, llm_calls_total
    global chat_stream_chunks_total, app_info, _registry
    try:
        from prometheus_client import (
            CollectorRegistry,
            Counter,
            Gauge,
            Histogram,
        )
    except ImportError:
        return False

    _registry = CollectorRegistry()

    http_requests_total = Counter(
        "tantan_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
        registry=_registry,
    )
    http_request_duration_seconds = Histogram(
        "tantan_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        registry=_registry,
    )
    llm_calls_total = Counter(
        "tantan_llm_calls_total",
        "Total LLM API calls",
        ["intent", "status"],
        registry=_registry,
    )
    chat_stream_chunks_total = Counter(
        "tantan_chat_stream_chunks_total",
        "Total chat SSE chunks yielded",
        ["intent"],
        registry=_registry,
    )
    app_info = Gauge(
        "tantan_app_info",
        "App build info (always 1; metadata in labels)",
        ["version", "environment"],
        registry=_registry,
    )
    return True


class PrometheusMiddleware(BaseHTTPMiddleware):
    """记录每个 HTTP 请求的计数 + 时长（按 path 模板聚合避免高基数）"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if http_requests_total is None:
            return await call_next(request)
        path_template = _get_path_template(request)
        method = request.method
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            try:
                http_requests_total.labels(
                    method=method,
                    path=path_template,
                    status=str(status_code),
                ).inc()
                http_request_duration_seconds.labels(
                    method=method,
                    path=path_template,
                ).observe(duration)
            except Exception:
                pass


def _get_path_template(request: Request) -> str:
    """从 request.scope["route"] 拿 path 模板（避免 /api/form/abc-123 撑爆 label）"""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


def metrics_endpoint(request: Request) -> Response:
    """`/metrics` 端点处理函数（FastAPI 会注入 Request）"""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    if _registry is None:
        return Response(content=b"", media_type=CONTENT_TYPE_LATEST)
    return Response(content=generate_latest(_registry), media_type=CONTENT_TYPE_LATEST)


def setup_metrics(app: Any) -> bool:
    """挂载 Prometheus 指标中间件 + /metrics 端点

    Args:
        app: FastAPI 应用

    Returns:
        True 表示已启用
    """
    global _metrics_initialized
    if _metrics_initialized:
        return True
    if not is_metrics_configured():
        return False
    if not _build_metrics():
        import logging
        logging.getLogger(__name__).warning(
            "METRICS_ENABLED=true 但缺 prometheus_client；跳过 metrics 初始化"
        )
        return False

    version = os.getenv("APP_VERSION", "0.1.0")
    environment = os.getenv("ENVIRONMENT", "development")
    app_info.labels(version=version, environment=environment).set(1)

    app.add_middleware(PrometheusMiddleware)
    app.add_route("/metrics", metrics_endpoint, methods=["GET"])
    _metrics_initialized = True
    return True


def record_llm_call(intent: str, status: str = "success") -> None:
    """业务代码钩子：记录一次 LLM 调用（缺包 / 未启用时静默 noop）"""
    if llm_calls_total is None:
        return
    try:
        llm_calls_total.labels(intent=intent, status=status).inc()
    except Exception:
        pass


def record_chat_stream_chunk(intent: str) -> None:
    """SSE 流式 chunk 计数"""
    if chat_stream_chunks_total is None:
        return
    try:
        chat_stream_chunks_total.labels(intent=intent).inc()
    except Exception:
        pass
