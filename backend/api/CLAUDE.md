# API Routes - REST API路由

FastAPI路由器，提供所有HTTP API端点。

## 路由前缀

所有路由挂载在 `/api` 前缀下。

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
- `POST /api/chat/stream` - 流式对话（SSE）

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

使用 `StateManager` (默认 `InMemoryStateManager`) 管理会话状态。
- 支持 Redis 模式（设置环境变量切换）
- 会话数据7天过期（可通过 SESSION_EXPIRE_SECONDS 环境变量配置）

## 文件上传验证

- 最大文件大小: 10MB (可通过环境变量配置)
- 允许的文件类型: `.xlsx`, `.xls`, `.pdf`, `.docx`, `.doc`, `.pptx`, `.md`
- MIME类型验证
- 文件名安全清理（防止路径遍历）

## 日志

关键操作均有结构化日志记录：
- 文件上传 (`/api/upload`)
- 表单确认 (`/api/form/{session_id}/section/{section}/confirm`)
- 对话消息 (`/api/chat`)
- 修改操作 (`/api/modify/{session_id}`)