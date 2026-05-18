"""
向量数据库客户端 - 碳管师收资系统
支持Milvus/Qdrant/PGVector三种向量数据库
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod

from tantan.backend.utils import get_logger

logger = get_logger(__name__)


def _validate_identifier(name: str) -> str:
    """验证并清理 SQL 标识符（表名、列名），防止 SQL 注入"""
    if not name or not isinstance(name, str):
        raise ValueError("标识符不能为空")
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"无效的标识符: {name}，只允许字母、数字和下划线，且必须以字母或下划线开头")
    if len(name) > 63:
        raise ValueError(f"标识符过长: {name}，最大长度为63个字符")
    return name


class VectorDBClient(ABC):
    """向量数据库抽象基类"""

    @abstractmethod
    def connect(self) -> bool:
        """连接数据库"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    def create_collection(self, name: str, dimension: int, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """创建集合"""
        pass

    @abstractmethod
    def delete_collection(self, name: str) -> bool:
        """删除集合"""
        pass

    @abstractmethod
    def insert(self, collection_name: str, vectors: List[List[float]], documents: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """插入向量"""
        pass

    @abstractmethod
    def search(self, collection_name: str, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """搜索向量"""
        pass

    @abstractmethod
    def delete(self, collection_name: str, ids: List[str]) -> bool:
        """删除向量"""
        pass


class MilvusClient(VectorDBClient):
    """Milvus向量数据库客户端"""

    def __init__(self, host: str = "localhost", port: int = 19530):
        self.host = host
        self.port = port
        self.client = None
        self.connected = False

    def connect(self) -> bool:
        """连接Milvus"""
        try:
            from pymilvus import connections
            connections.connect(host=self.host, port=self.port)
            self.connected = True
            return True
        except ImportError:
            raise ImportError(
                "pymilvus not installed. Please install it with: pip install pymilvus"
            )
        except Exception as e:
            logger.error(f"Milvus连接失败: {str(e)}", exc_info=True)
            return False

    def disconnect(self) -> None:
        """断开Milvus连接"""
        if self.connected:
            try:
                from pymilvus import connections
                connections.disconnect()
            except Exception:
                pass  # 忽略断开时的错误
            finally:
                self.connected = False

    def create_collection(self, name: str, dimension: int, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """创建Milvus集合"""
        if not self.connected:
            return False

        try:
            from pymilvus import Collection, CollectionSchema, FieldSchema, DataType

            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4000),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=4000)
            ]

            schema = CollectionSchema(fields=fields, description=metadata.get("description", "") if metadata else "")
            collection = Collection(name=name, schema=schema)

            # 创建索引
            index_params = {
                "metric_type": "IP",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            collection.create_index(field_name="vector", index_params=index_params)

            return True

        except Exception as e:
            logger.error(f"Milvus创建集合失败: collection={name}, error: {str(e)}", exc_info=True)
            return False

    def delete_collection(self, name: str) -> bool:
        """删除Milvus集合"""
        if not self.connected:
            return False

        try:
            from pymilvus import Collection
            collection = Collection(name)
            collection.drop()
            return True
        except Exception as e:
            logger.error(f"Milvus删除集合失败: collection={name}, error: {str(e)}", exc_info=True)
            return False

    def insert(self, collection_name: str, vectors: List[List[float]], documents: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """插入Milvus向量"""
        if not self.connected:
            return []

        try:
            from pymilvus import Collection, DataType
            import json

            collection = Collection(collection_name)
            collection.load()

            # 生成ID
            if ids is None:
                ids = [f"doc_{i}" for i in range(len(vectors))]

            # 准备数据
            data = [
                ids,
                vectors,
                [doc.get("content", "") for doc in documents],
                [json.dumps(doc.get("metadata", {})) for doc in documents]
            ]

            # 插入数据
            collection.insert(data)

            return ids

        except Exception as e:
            logger.error(f"Milvus插入向量失败: collection={collection_name}, error: {str(e)}", exc_info=True)
            return []

    def search(self, collection_name: str, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """搜索Milvus向量"""
        if not self.connected:
            return []

        try:
            from pymilvus import Collection
            import json

            collection = Collection(collection_name)
            collection.load()

            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}

            results = collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                output_fields=["content", "metadata"]
            )

            search_results = []
            for hits in results:
                for hit in hits:
                    search_results.append({
                        "id": hit.id,
                        "score": hit.score,
                        "content": hit.entity.get("content", ""),
                        "metadata": json.loads(hit.entity.get("metadata", "{}"))
                    })

            return search_results

        except Exception as e:
            logger.error(f"Milvus搜索向量失败: collection={collection_name}, error: {str(e)}", exc_info=True)
            return []

    def delete(self, collection_name: str, ids: List[str]) -> bool:
        """删除Milvus向量"""
        if not self.connected:
            return False

        try:
            from pymilvus import Collection
            collection = Collection(collection_name)
            collection.load()
            collection.delete(expr=f'id in {ids}')
            return True
        except Exception as e:
            logger.error(f"Milvus删除向量失败: collection={collection_name}, ids={ids}, error: {str(e)}", exc_info=True)
            return False


class QdrantClient(VectorDBClient):
    """Qdrant向量数据库客户端"""

    def __init__(self, host: str = "localhost", port: int = 6333):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}"
        self.client = None
        self.connected = False

    def connect(self) -> bool:
        """连接Qdrant"""
        try:
            import qdrant_client
            self.client = qdrant_client.QdrantClient(host=self.host, port=self.port)
            self.connected = True
            return True
        except ImportError:
            raise ImportError(
                "qdrant-client not installed. Please install it with: pip install qdrant-client"
            )
        except Exception as e:
            logger.error(f"Qdrant连接失败: {str(e)}", exc_info=True)
            return False

    def disconnect(self) -> None:
        """断开Qdrant连接"""
        self.connected = False

    def create_collection(self, name: str, dimension: int, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """创建Qdrant集合"""
        if not self.connected:
            return False

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import VectorParams, Distance

            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE)
            )
            return True

        except Exception as e:
            logger.error(f"Qdrant创建集合失败: collection={name}, error: {str(e)}", exc_info=True)
            return False

    def delete_collection(self, name: str) -> bool:
        """删除Qdrant集合"""
        if not self.connected:
            return False

        try:
            self.client.delete_collection(collection_name=name)
            return True
        except Exception as e:
            logger.error(f"Qdrant删除集合失败: collection={name}, error: {str(e)}", exc_info=True)
            return False

    def insert(self, collection_name: str, vectors: List[List[float]], documents: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """插入Qdrant向量"""
        if not self.connected:
            return []

        try:
            from qdrant_client.models import PointStruct

            if ids is None:
                ids = [f"doc_{i}" for i in range(len(vectors))]

            points = [
                PointStruct(
                    id=i,
                    vector=vector,
                    payload={
                        "content": doc.get("content", ""),
                        "metadata": doc.get("metadata", {})
                    }
                )
                for i, (vector, doc) in enumerate(zip(vectors, documents))
            ]

            self.client.upsert(collection_name=collection_name, points=points)
            return ids

        except Exception as e:
            logger.error(f"Qdrant插入向量失败: collection={collection_name}, error: {str(e)}", exc_info=True)
            return []

    def search(self, collection_name: str, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """搜索Qdrant向量"""
        if not self.connected:
            return []

        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k
            )

            return [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "content": hit.payload.get("content", ""),
                    "metadata": hit.payload.get("metadata", {})
                }
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Qdrant搜索向量失败: collection={collection_name}, error: {str(e)}", exc_info=True)
            return []

    def delete(self, collection_name: str, ids: List[str]) -> bool:
        """删除Qdrant向量"""
        if not self.connected:
            return False

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchKind

            self.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="id",
                            match=MatchKind(any=ids)
                        )
                    ]
                )
            )
            return True
        except Exception as e:
            logger.error(f"Qdrant删除向量失败: collection={collection_name}, ids={ids}, error: {str(e)}", exc_info=True)
            return False


class PGVectorClient(VectorDBClient):
    """PGVector向量数据库客户端"""

    def __init__(self, connection_string: str = "postgresql://postgres:postgres@localhost:5432/vector_db"):
        self.connection_string = connection_string
        self.engine = None
        self.connected = False

    def connect(self) -> bool:
        """连接PGVector"""
        try:
            from sqlalchemy import create_engine
            self.engine = create_engine(self.connection_string)
            self.connected = True
            return True
        except ImportError:
            raise ImportError(
                "sqlalchemy or psycopg2 not installed. "
                "Please install with: pip install sqlalchemy psycopg2-binary"
            )
        except Exception as e:
            logger.error(f"PGVector连接失败: {str(e)}", exc_info=True)
            return False

    def disconnect(self) -> None:
        """断开PGVector连接"""
        if self.engine:
            self.engine.dispose()
            self.connected = False

    def create_collection(self, name: str, dimension: int, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """创建PGVector表"""
        if not self.connected:
            return False

        try:
            from sqlalchemy import text

            # 验证表名防止 SQL 注入
            safe_name = _validate_identifier(name)

            # 验证维度是正整数
            if not isinstance(dimension, int) or dimension <= 0:
                raise ValueError(f"无效的向量维度: {dimension}")

            with self.engine.connect() as conn:
                # 启用向量扩展
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

                # 创建表（表名已验证，维度为整数）
                create_table_sql = text(f"""
                CREATE TABLE IF NOT EXISTS {safe_name} (
                    id VARCHAR(64) PRIMARY KEY,
                    vector vector({dimension}),
                    content TEXT,
                    metadata JSONB
                )
                """)
                conn.execute(create_table_sql)
                conn.commit()

                # 创建索引
                create_index_sql = text(f"""
                CREATE INDEX IF NOT EXISTS {safe_name}_vector_idx ON {safe_name} USING ivfflat (vector cosine_ops)
                """)
                conn.execute(create_index_sql)
                conn.commit()

            return True

        except Exception as e:
            logger.error(f"PGVector创建表失败: table={name}, error: {str(e)}", exc_info=True)
            return False

    def delete_collection(self, name: str) -> bool:
        """删除PGVector表"""
        if not self.connected:
            return False

        try:
            from sqlalchemy import text

            # 验证表名防止 SQL 注入
            safe_name = _validate_identifier(name)

            with self.engine.connect() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {safe_name}"))
                conn.commit()

            return True

        except Exception as e:
            logger.error(f"PGVector删除表失败: table={name}, error: {str(e)}", exc_info=True)
            return False

    def insert(self, collection_name: str, vectors: List[List[float]], documents: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """插入PGVector向量"""
        if not self.connected:
            return []

        try:
            from sqlalchemy import text
            import json

            # 验证表名防止 SQL 注入
            safe_name = _validate_identifier(collection_name)

            if ids is None:
                ids = [f"doc_{i}" for i in range(len(vectors))]

            with self.engine.connect() as conn:
                for id, vector, doc in zip(ids, vectors, documents):
                    vector_str = "[" + ",".join(str(v) for v in vector) + "]"
                    content = doc.get("content", "")
                    metadata = json.dumps(doc.get("metadata", {}))

                    # 使用参数化查询，表名已验证
                    conn.execute(
                        text(f"""
                        INSERT INTO {safe_name} (id, vector, content, metadata)
                        VALUES (:id, :vector::vector, :content, :metadata::jsonb)
                        ON CONFLICT (id) DO UPDATE SET vector = :vector::vector, content = :content, metadata = :metadata::jsonb
                        """),
                        {"id": id, "vector": vector_str, "content": content, "metadata": metadata}
                    )
                conn.commit()

            return ids

        except Exception as e:
            logger.error(f"PGVector插入向量失败: table={collection_name}, error: {str(e)}", exc_info=True)
            return []

    def search(self, collection_name: str, query_vector: List[float], top_k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """搜索PGVector向量"""
        if not self.connected:
            return []

        try:
            from sqlalchemy import text
            import json

            # 验证表名防止 SQL 注入
            safe_name = _validate_identifier(collection_name)

            # 验证 top_k 是正整数
            if not isinstance(top_k, int) or top_k <= 0:
                top_k = 5

            vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

            with self.engine.connect() as conn:
                results = conn.execute(
                    text(f"""
                    SELECT id, content, metadata, 1 - (vector <=> :vector::vector) as score
                    FROM {safe_name}
                    ORDER BY vector <=> :vector::vector
                    LIMIT :top_k
                    """),
                    {"vector": vector_str, "top_k": top_k}
                )

                return [
                    {
                        "id": row[0],
                        "score": row[3],
                        "content": row[1],
                        "metadata": json.loads(row[2]) if row[2] else {}
                    }
                    for row in results
                ]

        except Exception as e:
            logger.error(f"PGVector搜索向量失败: table={collection_name}, error: {str(e)}", exc_info=True)
            return []

    def delete(self, collection_name: str, ids: List[str]) -> bool:
        """删除PGVector向量"""
        if not self.connected:
            return False

        try:
            from sqlalchemy import text

            # 验证表名防止 SQL 注入
            safe_name = _validate_identifier(collection_name)

            if not ids:
                return True

            with self.engine.connect() as conn:
                # 使用参数化查询删除，避免 SQL 注入
                # 构建参数占位符
                placeholders = ", ".join([f":id_{i}" for i in range(len(ids))])
                params = {f"id_{i}": id_val for i, id_val in enumerate(ids)}

                conn.execute(
                    text(f"DELETE FROM {safe_name} WHERE id IN ({placeholders})"),
                    params
                )
                conn.commit()

            return True

        except Exception as e:
            logger.error(f"PGVector删除向量失败: table={collection_name}, ids={ids}, error: {str(e)}", exc_info=True)
            return False


class VectorDBFactory:
    """向量数据库工厂"""

    @staticmethod
    def create_client(db_type: Optional[str] = None) -> VectorDBClient:
        """
        创建向量数据库客户端

        Args:
            db_type: 数据库类型 (milvus/qdrant/pgvector)

        Returns:
            向量数据库客户端实例
        """
        from tantan.backend.config import get_config

        db_type = db_type or get_config().VECTOR_DB_TYPE

        if db_type == "milvus":
            return MilvusClient(
                host=get_config().MILVUS_HOST,
                port=get_config().MILVUS_PORT
            )
        elif db_type == "qdrant":
            return QdrantClient(
                host=get_config().QDRANT_HOST,
                port=get_config().QDRANT_PORT
            )
        elif db_type == "pgvector":
            return PGVectorClient(
                connection_string=get_config().PGVECTOR_CONN
            )
        else:
            raise ValueError(f"Unsupported vector DB type: {db_type}")


def get_vector_db_client() -> VectorDBClient:
    """获取向量数据库客户端"""
    return VectorDBFactory.create_client()
