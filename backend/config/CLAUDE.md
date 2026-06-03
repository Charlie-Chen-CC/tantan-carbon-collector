# Config - 配置管理

系统配置管理，支持环境变量和.env文件加载。

## 配置类

```python
class Config:
    # 阿里云API
    DASHSCOPE_API_KEY: Optional[str]

    # 数据库配置
    DATABASE_URL: str

    # 向量数据库配置
    VECTOR_DB_TYPE: str  # pgvector/milvus/qdrant
    MILVUS_HOST/PORT/COLLECTION
    QDRANT_HOST/PORT/COLLECTION
    PGVECTOR_CONN

    # 嵌入配置
    EMBEDDING_MODEL: str  # text-embedding-v2
    EMBEDDING_DIM: int    # 1536

    # LLM配置
    LLM_MODEL: str        # qwen-turbo
    LLM_TEMPERATURE: float
    LLM_MAX_TOKENS: int
```

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DASHSCOPE_API_KEY` | - | 阿里云API密钥（必填） |
| `DATABASE_URL` | PostgreSQL连接字符串 | 数据库地址 |
| `VECTOR_DB_TYPE` | pgvector | 向量数据库类型 |
| `REDIS_URL` | redis://localhost:6379/0 | Redis地址 |
| `ENVIRONMENT` | development | `production` 启用默认凭证启动检查（S5） |
| `REQUIRE_NON_DEFAULT_CREDENTIALS` | true | 生产环境禁止默认凭证 tantan_user/tantan_password |
| `COOKIE_SECURE` | false | 生产 True（HTTPS only）；dev False（HTTP） |
| `COOKIE_SAMESITE` | strict | CSRF 防御；可设 `lax`/`none` |

## 验证

```python
Config.validate()  # 检查必填项
Config.is_llm_available()      # 检查LLM是否可用
Config.is_vector_db_available()  # 检查向量数据库是否可用
```