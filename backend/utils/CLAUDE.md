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

在异步环境中传递 trace_id：

```python
from tantan.backend.utils import TraceContext, get_trace_id

# 设置 trace_id
TraceContext.set_trace_id("request-123")

# 在其他模块获取
trace_id = get_trace_id()  # 返回 "request-123"
```

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LOG_LEVEL` | INFO | 日志级别 (DEBUG/INFO/WARNING/ERROR) |
| `LOG_JSON` | false | 是否使用 JSON 格式 |

## 日志文件

日志文件存储在 `logs/app.log`，支持日志轮转（需要自行配置）。