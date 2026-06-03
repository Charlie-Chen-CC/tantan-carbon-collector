# Backend - FastAPI后端服务

## 概述

碳管师收资系统的后端服务，提供REST API和AI能力。

## 目录结构

```
backend/
├── main.py              # FastAPI应用入口
├── config/              # 配置管理
├── models/              # 数据库模型 (SQLAlchemy)
├── agents/              # AI Agent模块
│   └── form_filler/     # Phase 2.5 拆分的 FormFillAgent 包
│       ├── __init__.py
│       ├── agent.py
│       ├── mapping.py
│       ├── transformers.py
│       ├── section_defs.py
│       └── guides.py
├── api/                 # API路由（Phase 2.4 拆分）
│   ├── routes.py        # 聚合器（< 50 行）
│   ├── auth.py
│   ├── auth_router.py   # 实际挂在 /api/auth
│   ├── sessions_router.py
│   ├── files_router.py
│   ├── extract_router.py
│   ├── form_router.py
│   ├── chat_router.py
│   ├── history_router.py
│   ├── validation.py    # python-magic 文件验证
│   └── models.py        # Pydantic 模型
├── rag/                 # RAG知识库检索
│   ├── ali_llm.py       # 直接调 dashscope SDK（Phase 2.6 去掉 LangChain 包装）
│   ├── retriever.py     # RAG 检索 + LLM 管道（Phase 2.6 重写去 LCEL）
│   ├── vector_db.py     # PGVector / Milvus / Qdrant 客户端
│   └── knowledge_base.py
├── state/               # 状态管理（统一 DatabaseStateManager）
├── queue/               # Phase 5 待重建（Celery）
└── .venv/               # Python虚拟环境
```

## 核心模块

### agents/ - AI Agent
- `file_extractor.py` - Excel/文件数据提取Agent（Section 1-9 专精提示词）
- `form_filler/` - 表单填充Agent（Phase 2.5 拆为 5 个模块：agent/mapping/transformers/section_defs/guides）
- `qa_agent.py` - 问答Agent（支持RAG检索）
- `modify_agent.py` - 表单修改验证Agent
- `file_processor.py` - 批量文件处理（保留）

### rag/ - RAG知识库
- `ali_llm.py` - 阿里云 DashScope SDK 直接封装（Phase 2.6 起，**不再走 LangChain**）
- `retriever.py` - RAG 检索 + LLM 管道（Phase 2.6 重写去 LCEL，手工实现 RAG 链）
- `vector_db.py` - PGVector / Milvus / Qdrant 客户端直连（无需 LangChain 适配层）
- `knowledge_base.py` - 知识库管理

### api/ - 路由（Phase 2.4 拆分）
- `routes.py` - 聚合器（22 行）
- `auth_router.py` - 鉴权（注册/登录/登出/me）
- `sessions_router.py` - 会话管理
- `files_router.py` - 文件上传/下载/列表/删除
- `extract_router.py` - 文件提取（单文件 + 批量 SSE）
- `form_router.py` - 表单 CRUD
- `chat_router.py` - 聊天 + 修改
- `history_router.py` - 操作历史
- `validation.py` - python-magic 真实 MIME 探测
- `models.py` - Pydantic 请求/响应模型

## 启动方式

```bash
# 从workspace目录 (tantan的父目录) 运行
cd tantan的父目录
source tantan/backend/.venv/Scripts/activate
python -m tantan.backend.main --port 8000
# 访问 http://localhost:8000/docs 查看API文档
```

## 环境变量

- `ALLOWED_ORIGINS` - CORS 允许的前端域名，逗号分隔。**dev 默认** `http://localhost:3000..3010`（含 start.sh 探测区间），**生产必须显式设置**否则启动 fail-fast
- `ENVIRONMENT` - `development` / `production`；生产模式强制 ALLOWED_ORIGINS 显式
- `SESSION_EXPIRE_SECONDS` - 会话过期时间（秒），默认为 86400*7 (7天)

## 状态管理

- 统一使用 `DatabaseStateManager`（PostgreSQL 持久化），无内存/Redis 分支
- 会话默认7天过期（通过 `created_at` + 应用层清理）

## 日志

后端使用统一的日志系统 (`tantan.backend.utils.logger`)：

- **请求追踪**：每个请求有唯一 `trace_id`，可在日志中追踪完整调用链
- **结构化日志**：输出到控制台和 `logs/app.log`，支持 JSON 格式
- **中间件**：`RequestLoggingMiddleware` 自动记录请求/响应和异常堆栈
- **日志级别**：通过环境变量 `LOG_LEVEL` 配置 (DEBUG/INFO/WARNING/ERROR)

```python
from tantan.backend.utils import get_logger

logger = get_logger(__name__)
logger.error("操作失败", exc_info=True)
```

## 编码规范

### 禁止 try/except 静默吞错

不允许写这样的代码：

```python
try:
    result = some_call()
except Exception:
    pass  # 静默吞错
```

正确做法（**三选一**）：

1. **必须处理** → `except SpecificException as e: logger.warning(...)`；最起码留痕
2. **让上游接管** → 直接 `raise` 或 `raise NewException(...) from e`
3. **确认无害** → 注释里写明"为什么吞这个错是安全的"（必须有 `logger.debug` 留痕）

不允许 `except Exception: pass` / `except: pass` / `except: continue` / `except Exception: return None` 这几种模式。
若必须返回 fallback（如 RAG 检索无结果返回空列表），应用 `logger.debug` 记一行再返回，且不让 fallback 伪装成成功。

### 错误处理统一

- 业务异常统一用 `AppException(ErrorCode, user_message, developer_message)`，见 `tantan/backend/utils/exceptions.py`
- `developer_message` 记日志即可，绝不出现在响应体
- 全局 `@app.exception_handler(Exception)` 兜底统一返回 `{error_code: INTERNAL_ERROR, user_message: "服务暂时不可用"}`

## 数据库

使用PostgreSQL，通过SQLAlchemy ORM管理。需要提前创建数据库和用户。

## 字段映射

`FormFillAgent` 类维护了完整的中文字段名到前端英文字段名的映射：

```python
class FormFillAgent:
    BACKEND_TO_FRONTEND_FIELD_MAP = {
        "企业名称": "enterpriseName",
        "所属行业": "industry",
        # ... 完整映射约100+字段
    }
```

**添加新字段时必须同时更新**（**字段映射 SSOT** 原则，避免前后端字段漂移）：
1. `agents/form_filler/section_defs.py` 中 `section_definitions` 的字段定义
2. `agents/form_filler/mapping.py` 中 `BACKEND_TO_FRONTEND_FIELD_MAP` 映射表
3. 若为多行动态字段，还需 `agents/form_filler/transformers.py` 中 `MULTI_ROW_TRANSFORMERS`
4. 前端 `tantan/frontend/config/sectionConfig.ts` 中 `SECTION_FIELDS` 配置

**禁止**只改后端不改正向映射，或只改前端不改正向映射——任何一端缺字段都会导致数据 silent drift。Phase 6.2 计划从 `shared/field_schema.json` 单一来源 codegen 前后端两端的字段配置。

## 测试

```bash
cd tantan的父目录
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests --tb=short
```