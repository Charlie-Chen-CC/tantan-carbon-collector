# Backend - FastAPI后端服务

## 概述

碳管师收资系统的后端服务，提供REST API和AI能力。

## 目录结构

```
backend/
├── main.py           # FastAPI应用入口
├── config/           # 配置管理
├── models/           # 数据库模型 (SQLAlchemy)
├── agents/           # AI Agent模块 (LangGraph)
├── api/              # API路由
├── rag/              # RAG知识库检索
├── state/            # 状态管理 (Redis/内存)
├── queue/            # Celery任务队列
├── knowledge_base/   # 知识库文件
└── venv/             # Python虚拟环境
```

## 核心模块

### agents/ - AI Agent
- `orchestrator.py` - 表单填报编排Agent (LangGraph StateGraph)
- `file_extractor.py` - Excel文件数据提取Agent
- `form_filler.py` - 表单填充Agent
- `qa_agent.py` - 问答Agent (支持RAG检索)
- `modify_agent.py` - 表单修改验证Agent

### rag/ - RAG知识库
- `ali_llm.py` - 阿里云LLM/Embedding封装
- `langchain_llm.py` - LangChain兼容接口
- `langchain_vectorstore.py` - 向量数据库适配
- `retriever.py` - RAG检索管道
- `vector_db.py` - 向量数据库客户端
- `knowledge_base.py` - 知识库管理

### api/
- `routes.py` - 所有REST API路由

## 启动方式

```bash
cd backend
source venv/Scripts/activate
python main.py
# 访问 http://localhost:8000/docs 查看API文档
```

## 环境变量

- `ALLOWED_ORIGINS` - CORS允许的前端域名，逗号分隔，默认为 `http://localhost:3000`
- `SESSION_EXPIRE_SECONDS` - 会话过期时间（秒），默认为 86400*7 (7天)

## 状态管理

- 开发环境使用 `InMemoryStateManager` (内存)
- 生产环境使用 `RedisStateManager` (需要启动Redis)
- 会话默认7天过期（可通过环境变量配置）

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

## 数据库

使用PostgreSQL，通过SQLAlchemy ORM管理。需要提前创建数据库和用户。