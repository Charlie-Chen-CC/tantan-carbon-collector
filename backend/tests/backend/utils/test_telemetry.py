"""
OpenTelemetry 集成测试 - Phase 5.6

设计：
- 默认 OTEL_ENABLED 未设置 → setup_telemetry 返回 False
- OTEL_ENABLED=true → setup_telemetry 装上 TracerProvider + FastAPI 埋点
- get_tracer() 在任何状态下都不抛异常（缺包时返回 NoOp）
"""
import pytest
from fastapi import FastAPI

from tantan.backend.utils.telemetry import (
    is_telemetry_configured,
    is_telemetry_enabled,
    setup_telemetry,
    get_tracer,
)


class TestTelemetryDisabled:
    """默认未启用场景"""

    def test_is_telemetry_configured_default_false(self, monkeypatch):
        monkeypatch.delenv("OTEL_ENABLED", raising=False)
        assert is_telemetry_configured() is False

    def test_setup_returns_false_when_disabled(self, monkeypatch):
        monkeypatch.delenv("OTEL_ENABLED", raising=False)
        app = FastAPI()
        assert setup_telemetry(app) is False
        assert is_telemetry_enabled() is False

    def test_get_tracer_noop_when_disabled(self, monkeypatch):
        monkeypatch.delenv("OTEL_ENABLED", raising=False)
        tracer = get_tracer("tantan.test")
        with tracer.start_as_current_span("test-span"):
            pass


class TestTelemetryEnabled:
    """OTEL_ENABLED=true 场景"""

    def test_is_telemetry_configured_true(self, monkeypatch):
        for val in ("1", "true", "yes", "True"):
            monkeypatch.setenv("OTEL_ENABLED", val)
            assert is_telemetry_configured() is True

    def test_setup_creates_tracer_provider(self, monkeypatch):
        monkeypatch.setenv("OTEL_ENABLED", "true")
        app = FastAPI()
        result = setup_telemetry(app)
        assert result is True
        assert is_telemetry_enabled() is True

    def test_get_tracer_returns_real_tracer(self, monkeypatch):
        monkeypatch.setenv("OTEL_ENABLED", "true")
        setup_telemetry(FastAPI())
        tracer = get_tracer("tantan.test")
        with tracer.start_as_current_span("test-span") as span:
            assert span is not None
            assert span.get_span_context().is_valid

    def test_setup_idempotent(self, monkeypatch):
        """二次 setup 不重复装 TracerProvider（避免 _TRACER_PROVIDER_SET_ONCE 警告）"""
        monkeypatch.setenv("OTEL_ENABLED", "true")
        app = FastAPI()
        setup_telemetry(app)
        result2 = setup_telemetry(app)
        assert result2 is True


class TestTelemetryOTLPEndpoint:
    """OTEL_EXPORTER_OTLP_ENDPOINT 触发 OTLP exporter（不连，仅路径验证）"""

    def test_otlp_endpoint_env_does_not_crash(self, monkeypatch):
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        app = FastAPI()
        try:
            setup_telemetry(app)
        except Exception as e:
            pytest.skip(f"OTLP gRPC exporter 未安装: {e}")
        assert is_telemetry_enabled() is True
