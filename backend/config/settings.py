"""
配置管理 - 碳管师收资系统
支持从环境变量和.env文件加载配置
"""

import os
from typing import Optional
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class Config:
    """配置类"""

    # 阿里云 API
    DASHSCOPE_API_KEY: Optional[str] = os.getenv("DASHSCOPE_API_KEY")

    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://tantan_user:tantan_password@localhost:5432/tantan")

    # 向量数据库配置
    VECTOR_DB_TYPE: str = os.getenv("VECTOR_DB_TYPE", "pgvector")
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "carbon_knowledge")

    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "carbon_knowledge")

    PGVECTOR_CONN: str = os.getenv("PGVECTOR_CONN", "postgresql://postgres:postgres@localhost:5432/vector_db")

    # 向量嵌入配置
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v2")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    # LLM配置
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen-turbo")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否完整"""
        errors = []

        if not cls.DASHSCOPE_API_KEY:
            errors.append("DASHSCOPE_API_KEY is required")

        if cls.VECTOR_DB_TYPE not in ["milvus", "qdrant", "pgvector"]:
            errors.append("VECTOR_DB_TYPE must be one of: milvus, qdrant, pgvector")

        if errors:
            print(f"Configuration errors: {errors}")
            return False

        return True

    @classmethod
    def is_llm_available(cls) -> bool:
        """检查LLM是否可用"""
        return bool(cls.DASHSCOPE_API_KEY)

    @classmethod
    def is_vector_db_available(cls) -> bool:
        """检查向量数据库是否可用"""
        return bool(cls.VECTOR_DB_TYPE)


# 全局配置实例
config = Config()


def get_config() -> Config:
    """获取配置实例"""
    return config
