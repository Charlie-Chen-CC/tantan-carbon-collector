# Utils - 工具模块

通用工具模块，提供日志、追踪等基础设施。

## logger - 日志工具

### 核心功能

- **trace_id 追踪**：每个请求有唯一 UUID，可在日志中追踪完整调用链
- **结构化日志**：支持普通格式和 JSON 格式日志
- **文件输出**：同时输出到控制台和 `logs/app.log`
- **异常堆栈**：自动记录完整 traceback

### 使用方式

```python
from tantan.backend.utils import get_logger

logger = get_logger(__name__)

# 记录错误
try:
    result = some_function()
except Exception as e:
    log_exception(logger, e, {"session_id": session_id, "section": section})
    # 或直接
    logger.error(f"操作失败: {str(e)}", exc_info=True)

# 记录普通信息
logger.info(f"处理请求: session_id={session_id}")
```

### 日志格式

```
2026-05-15T10:30:00.123456 | abc123-def456 | ERROR     | backend.agents.qa_agent | AI响应失败: Connection timeout | {traceback...}
```

JSON 格式：
```json
{"timestamp": "2026-05-15T10:30:00.123456", "level": "ERROR", "trace_id": "abc123-def456", "module": "qa_agent", "message": "AI响应失败", "stack_trace": "..."}
```

### TraceContext

在异步环境中传递 trace_id（Phase 5.4 起改用 `contextvars.ContextVar`）：

```python
from tantan.backend.utils import TraceContext, get_trace_id

# 设置 trace_id（返回 Token，reset 时需用）
token = TraceContext.set_trace_id("request-123")
try:
    # 在其他模块获取
    trace_id = get_trace_id()  # 返回 "request-123"
finally:
    TraceContext.reset(token)
```

**为什么改 contextvars**：
- 原 `threading.local` 在 async 场景下有问题：asyncio.Task 跨 await 边界可能调度到不同线程（`run_in_executor`），threading.local 不会跨线程传播
- `ContextVar` 随 `Task` 一起被 `copy_context()` 捕获，`create_task` / `gather` 都自动继承父 task 的 trace_id
- `set_trace_id` 返回 `Token`，`reset(token)` 是栈式还原；`clear()` 仅清回 None，**不**还原到 set 之前的状态（保留旧 API 兼容）

**与 `RequestLoggingMiddleware` 配合**：
- 中间件 `set_trace_id` 拿 token，`finally` 里 `reset(token)`，异常路径不污染下一个请求

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LOG_LEVEL` | INFO | 日志级别 (DEBUG/INFO/WARNING/ERROR) |
| `LOG_JSON` | false | 是否使用 JSON 格式 |

## 日志文件

日志文件存储在 `logs/app.log`，支持日志轮转（需要自行配置）。

## telemetry - OpenTelemetry 追踪 (Phase 5.6)

**默认关闭**。`OTEL_ENABLED=true` 才启用，启用后：
- `TracerProvider` 装上 `service.name=tantan-backend`（可被 `OTEL_SERVICE_NAME` 覆盖）
- `ConsoleSpanExporter` 输出到 stdout；`OTEL_EXPORTER_OTLP_ENDPOINT` 切到 OTLP gRPC exporter
- `FastAPIInstrumentor.instrument_app(app)` 自动给每个请求建 span

### 用法

```python
from tantan.backend.utils import setup_telemetry, get_tracer, is_telemetry_enabled

# main.py
if is_telemetry_configured():
    setup_telemetry(app)

# 业务代码：手动开 span（OTel 未启用时 get_tracer() 返回 NoOp）
tracer = get_tracer(__name__)
with tracer.start_as_current_span("extract_section") as span:
    span.set_attribute("section", 3)
    # ... do work
```

### 设计要点
- `setup_telemetry` 幂等（多次调用安全）
- `is_telemetry_enabled()` 用于测试断言
- `get_tracer()` 在缺包时返回 NoOp（永不让 OTel 缺包导致 import 失败）

### 与 TraceContext 关系
- `TraceContext`（Phase 5.4 contextvars）管应用层 trace_id
- OTel 另起一个 trace_id，由 W3C `traceparent` header 串联
- 两者**并存**而非替代：日志里看到的 `trace_id` 是 TraceContext，OTel 看到的是它自己的；如需打通可在 OTel processor 里把 TraceContext.trace_id 注入 span attribute

## metrics - Prometheus 指标 (Phase 5.7)

**默认关闭**。`METRICS_ENABLED=true` 才启用，启用后：
- 挂 `PrometheusMiddleware` 计数每次 HTTP 请求（按 path 模板聚合避免高基数）
- 暴露 `GET /metrics` 端点（Prometheus 抓取）
- 业务侧可调 `record_llm_call(intent, status)` / `record_chat_stream_chunk(intent)` 增加自定义计数

### 关键指标

| 指标名 | 类型 | 标签 | 用途 |
|--------|------|------|------|
| `tantan_http_requests_total` | Counter | method/path/status | 请求计数 |
| `tantan_http_request_duration_seconds` | Histogram | method/path | 请求时长（桶 10ms-10s） |
| `tantan_llm_calls_total` | Counter | intent/status | LLM 调用计数 |
| `tantan_chat_stream_chunks_total` | Counter | intent | SSE chunk 计数 |
| `tantan_app_info` | Gauge | version/environment | 元信息（恒为 1） |

### 用法

```python
from tantan.backend.utils import setup_metrics, record_llm_call, record_chat_stream_chunk

# main.py
if is_metrics_configured():
    setup_metrics(app)

# 业务代码
record_llm_call("professional_question", "success")
record_chat_stream_chunk("chitchat")
```

### 设计要点
- **独立 CollectorRegistry**（不用全局默认）：避免 reload / 多次 setup 时 `Duplicated timeseries`
- **path 模板聚合**：用 `request.scope["route"].path` 而不是 `request.url.path`，避免 `/api/form/abc-123` 撑爆 label
- **缺包 NoOp**：`prometheus_client` 缺失时 `record_*` 是静默 noop，不让监控组件缺失导致业务崩溃

## ratelimit - 速率限制 (Phase 5.8 / S3)

**默认开启**。`RATELIMIT_ENABLED=false` 关闭。slowapi 内存 Limiter。

### 默认策略

| 名称 | 限制 | 用途 |
|------|------|------|
| `GLOBAL_DEFAULT` | 200/min per IP | 全局中间件兜底 |
| `AUTH_DEFAULT` | 5/min per IP | 登录/注册防爆破 |
| `UPLOAD_DEFAULT` | 10/min per IP | 文件上传 |
| `CHAT_DEFAULT` | 30/min per IP | 聊天 |

### 用法

```python
from tantan.backend.utils import limit_auth, limit_upload, limit_chat

@router.post("/login")
@limit_auth
async def login(...):
    ...
```

### 设计要点
- **Limiter 在 import 时构造**：装饰器需要 module-level limiter，否则 `@limit_auth` 装饰时拿到 None 变 noop
- **被装饰的 endpoint 必须有 `request: Request` 和 `response: Response` 参数**（slowapi header 注入要求）
- 触发限流：返回 **429 + Retry-After 头**
- 多 worker 部署需切 Redis storage：`_limiter = Limiter(..., storage_uri="redis://...")`
- 缺包时 noop：装饰器直接返回原函数，setup 跳过