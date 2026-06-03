"""
OpenTelemetry 追踪 - 碳管师收资系统 (Phase 5.6)

设计：
- **默认关闭**（OTEL_ENABLED=true 才启用）
- 启用时设置 TracerProvider + FastAPIInstrumentor
- ConsoleSpanExporter 用于开发，OTLP 通过 OTEL_EXPORTER_OTLP_ENDPOINT 切换
- trace_id 与 Phase 5.4 的 TraceContext 共享：OTel 在 set_tracer_provider 时
  TraceContextTextMapPropagator 优先从 W3C traceparent header 抽取，否则自己生成
- 测试用 is_telemetry_enabled() 跳过断言
"""
import os
from typing import Any, Optional

_telemetry_initialized: bool = False


def is_telemetry_enabled() -> bool:
    """是否启用了 OpenTelemetry"""
    return _telemetry_initialized


def is_telemetry_configured() -> bool:
    """环境变量是否请求启用 telemetry（用于 setup 前判断）"""
    return os.getenv("OTEL_ENABLED", "").lower() in ("1", "true", "yes")


def setup_telemetry(app: Any) -> bool:
    """初始化 OpenTelemetry。

    Args:
        app: FastAPI 应用实例（启用 FastAPI 自动埋点时需要）

    Returns:
        True 表示已启用；False 表示跳过（默认或缺包）
    """
    global _telemetry_initialized
    if _telemetry_initialized:
        return True
    if not is_telemetry_configured():
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )
    except ImportError as e:
        import logging
        logging.getLogger(__name__).warning(
            f"OTEL_ENABLED=true 但缺 opentelemetry 包: {e}; 跳过 telemetry 初始化"
        )
        return False

    service_name = os.getenv("OTEL_SERVICE_NAME", "tantan-backend")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)))
        except ImportError:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except ImportError as e:
        import logging
        logging.getLogger(__name__).warning(
            f"opentelemetry-instrumentation-fastapi 未安装: {e}; 跳过 FastAPI 埋点"
        )

    _telemetry_initialized = True
    return True


def get_tracer(name: str) -> Any:
    """获取 tracer（OTel 启用时返回真实 tracer，否则返回 NoOp tracer）"""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        class _NoOpTracer:
            def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
                from contextlib import nullcontext
                return nullcontext()
        return _NoOpTracer()
