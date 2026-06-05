# API Routes - REST API路由

FastAPI路由器，提供所有HTTP API端点。

## 路由前缀

所有路由挂载在 `/api` 前缀下。

**Phase 2.4 拆分结构**（`routes.py` 仅 22 行聚合器）：
- `auth_router.py` - `/api/auth/*` 鉴权端点（注册/登录/登出/me/profile）
- `sessions_router.py` - `/api/session` + `/api/sessions`
- `files_router.py` - `/api/upload` + `/api/task/{id}` + `/api/files/*`
- `extract_router.py` - `/api/extract/{session}/section/{n}` + `/batch` (SSE)
- `form_router.py` - `/api/form/{session}` + `/form/{session}/section/{n}` (GET/PATCH/POST)
- `chat_router.py` - `/api/chat` + `/api/chat/stream` + `/api/modify/{session}`
- `history_router.py` - `/api/history/{session}`

**辅助文件**：
- `validation.py` - python-magic 真实 MIME 探测（被 files_router 调用）
- `models.py` - Pydantic 请求/响应模型集中位置

## 主要端点

### 会话管理
- `POST /api/session` - 创建新会话
- `GET /api/session/{session_id}` - 获取会话状态

### 文件操作
- `POST /api/upload` - 上传文件
- `GET /api/task/{task_id}` - 获取任务状态

### 表单操作
- `GET /api/form/{session_id}` - 获取表单状态
- `PATCH /api/form/{session_id}/section/{section}` - 更新部分数据
- `POST /api/form/{session_id}/section/{section}/confirm` - 确认部分完成
- `POST /api/form/{session_id}/current-section` - 切换当前部分

### 文件提取
- `POST /api/extract/{session_id}/section/{section}` - 提取文件中特定部分数据

### AI对话
- `POST /api/chat` - 发送消息（非流式）
- `POST /api/chat/stream` - 流式对话（SSE，**Phase 5.3 真实流式**：LLM token-by-token）

**Phase 5.3 真实流式说明**：
- 之前：等 `generate_response()` 整段返回后再按 10 字符切片 yield，user 看到的"流式"是假的
- 现在：`QAAgent.generate_response_stream()` 同步生成器，事件序列 `intent → message(×N) → done`
- LLM 流式：`_stream_llm_chat` 直接调 `AliLLMClient.chat(stream=True)`，逐 token yield
- 规则回答（guidance / chitchat）：一次性 yield 整段
- RAG 流式：调 `RAGPipeline.answer_stream()` 已有实现
- 响应类：`StreamingResponse + ServerSentEvent.encode()`（**不用 `EventSourceResponse`**，sse_starlette 1.8+ 内部 `AppStatus.should_exit_event` 类级 anyio.Event 跨测试时会绑到已关闭的 event loop）

### 修改
- `POST /api/modify/{session_id}` - 修改表单数据

### 历史
- `GET /api/history/{session_id}` - 获取操作历史

## 请求模型

```python
class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = None

class ModifyRequest(BaseModel):
    section: int
    field: str
    old_value: Any
    new_value: Any
    reason: Optional[str] = ""
```

## 状态管理器

使用 `StateManager` (代理到 `DatabaseStateManager`) 管理会话状态。
- 统一用 PostgreSQL 持久化
- 会话数据7天过期（可通过 SESSION_EXPIRE_SECONDS 环境变量配置）

## 认证

- **httpOnly Cookie** 是唯一认证方式：`Set-Cookie: auth_token=...; HttpOnly; Secure(prod); SameSite=Strict; Max-Age=604800; Path=/`
- `get_current_user` 依赖注入从 `auth_token` cookie 读 token，不再支持 Bearer Authorization 头
- 旧接口 `get_current_user_from_cookie` 仍保留作 no-op alias
- Redis 仍是 token 存储后端（dev 环境降级到内存）；client 端完全无 token 概念

## 文件上传验证

- 最大文件大小: 10MB (硬编码 `MAX_FILE_SIZE` 常量)
- 允许的文件类型: `.xlsx`, `.xls`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.md`, `.png`, `.jpg`, `.jpeg`
- **真实 MIME 探测**：使用 `python-magic` (即 `python-magic-bin==0.4.14` Windows 平台二进制) 读取文件前 2KB 探测真实 MIME
- **扩展名 ↔ MIME 双向校验**：`EXT_TO_MIMES` 字典维护每个扩展名对应的真实 MIME 白名单，防止「扩展名白名单 + 实际内容是 PE 可执行文件」的攻击
- **UUID 文件名重写**：上传文件用 `uuid.uuid4().hex` 重新命名，丢弃客户端原始文件名（防止路径遍历 + 防止泄露用户隐私）
- **P0-3 修复（2026-06-04）**：上传路径用 `f"{file_id}_{ext}"`（带 `_` 前缀）匹配下载 `filename.startswith(file_id + "_")` 约定。重构前 06-03 引入 1 行 bug 导致 GET /api/files/{file_id} 永远 404。回归测试：`test_files.py::TestUpload::test_upload_then_download_roundtrip`

## 日志

关键操作均有结构化日志记录：
- 文件上传 (`/api/upload`)
- 表单确认 (`/api/form/{session_id}/section/{section}/confirm`)
- 对话消息 (`/api/chat`)
- 修改操作 (`/api/modify/{session_id}`)

## 错误处理（S3.12 统一体系 / P0-1 完成 2026-06-04）

- 旧散乱 `return {"error": str(e)}` / `HTTPException(400, str(e))` **已废弃**
- 新体系：`AppException(ErrorCode, user_message, developer_message)` 详见 `tantan/backend/utils/exceptions.py`
- 响应体只暴露 `error_code` + `user_message`；`developer_message` 仅写日志（绝不在响应中出现）
- 全局 `@app.exception_handler(Exception)` 兜底：未捕获异常统一返回 `{error_code: INTERNAL_ERROR, user_message: "服务暂时不可用"}`，绝不向客户端泄露堆栈/SQL/路径
- 前端 `services/api.ts` 拦截器把 `user_message` 挂到 error 对象 (`error.appUserMessage`)，业务层 catch 时可直接 `message.error(err.appUserMessage)`
- 新增业务异常时：先在 `ErrorCode` 枚举加值，再 `raise AppException(ErrorCode.X, user_msg)`，不要直接 raise HTTPException
- 全部 8 个 router 文件（auth/chat/extract/files/form/history/sessions/validation）已 100% 切换到 `AppException`（P0-1 修复 2026-06-04）
- AST 守门测试：`tantan/backend/tests/backend/api/test_exceptions.py`
  - `TestRoutersUseAppException::test_no_http_exception_in_router` 8 个文件 0 HTTPException
  - `TestNoStrELeakInRaises::test_no_str_call_in_user_visible_params` 8 个文件 user_message/detail 不含 `str(...)`
  - `TestAppExceptionResponseShape` 验证响应体不含 `developer_message`

### 4xx 错误码使用规范

| 错误码 | 用途 | 示例 |
|--------|------|------|
| `INVALID_REQUEST` | 通用 400 | "用户名已存在" |
| `AUTH_REQUIRED` | 401 未登录 | "未登录或Token已过期" |
| `AUTH_INVALID_CREDENTIALS` | 401 用户名/密码错 | "用户名或密码错误" |
| `AUTH_TOKEN_EXPIRED` | 401 Token 过期 | "Token已过期，请重新登录" |
| `AUTH_USER_DISABLED` | 401 用户被禁 | "用户已被禁用" |
| `SESSION_NOT_FOUND` | 404 会话不存在 | - |
| `SESSION_INVALID_SECTION` | 400 section 编号 1-9 之外 | "无效的部分编号（1-9）" |
| `FILE_TOO_LARGE` | 400 文件超 10MB | - |
| `UNSUPPORTED_FILE_TYPE` | 400 扩展名不在白名单 | - |
| `FILE_EMPTY` | 400 空文件 / 读不出 | - |
| `FILE_CONTENT_MISMATCH` | 400 MIME 与扩展名不符 | - |
| `FILE_NOT_FOUND` | 404 文件不存在 | - |
| `EXTRACTION_FAILED` | 400 提取失败 | - |
| `OPERATION_NOT_ALLOWED` | 403 无权操作 | "无权访问/删除此文件" |
| `INTERNAL_ERROR` | 500 兜底（必须 `developer_message=str(e)`） | "服务暂时不可用，请稍后重试" |

### 写法示例

```python
# 4xx - 用户可见错误
raise AppException(
    ErrorCode.SESSION_NOT_FOUND,
    "会话不存在",
    status_code=404,
)

# 4xx - 携带额外上下文
raise AppException(
    ErrorCode.UNSUPPORTED_FILE_TYPE,
    f"不支持的文件类型: {ext}，仅支持 xlsx/xls/pdf/docx/doc/pptx/md/png/jpg/jpeg",
    status_code=400,
)

# 5xx - 内部错误，dev_msg 写日志
raise AppException(
    ErrorCode.INTERNAL_ERROR,
    "AI响应失败，请稍后重试",
    status_code=500,
    developer_message=str(e),  # 仅入日志，绝不返给前端
)

# SSE error 事件也走 user_message
yield ServerSentEvent(event="error", data=json.dumps({
    "error_code": ErrorCode.INTERNAL_ERROR.value,
    "user_message": "批量提取失败，请稍后重试"
}))
```