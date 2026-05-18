"""
LangChain VectorStore 适配层 - 碳管师收资系统
将现有 VectorDBClient 适配为 LangChain VectorStore 接口
"""

from typing import List, Dict, Any, Optional, Callable
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore, VectorStoreRetriever

from tantan.backend.config import get_config
from tantan.backend.utils import get_logger

logger = get_logger(__name__)


class LangChainVectorStoreAdapter(VectorStore):
    """
    适配现有 VectorDBClient 到 LangChain VectorStore 接口
    保留原有客户端逻辑，适配 LangChain 接口
    """

    def __init__(
        self,
        embedding,  # LangChain embedding function
        db_type: Optional[str] = None,
        collection_name: Optional[str] = None,
        **kwargs
    ):
        self.embedding = embedding
        self.db_type = db_type or get_config().VECTOR_DB_TYPE
        self.collection_name = collection_name or self._get_collection_name()
        self._client = None
        self._init_client(kwargs)

    def _get_collection_name(self) -> str:
        if self.db_type == "milvus":
            return get_config().MILVUS_COLLECTION
        elif self.db_type == "qdrant":
            return get_config().QDRANT_COLLECTION
        return "carbon_knowledge"

    def _init_client(self, kwargs):
        """初始化底层向量数据库客户端"""
        try:
            if self.db_type == "milvus":
                from langchain_milvus import MilvusVectorStore
                self._client = MilvusVectorStore(
                    embedding=self.embedding,
                    collection_name=self.collection_name,
                    connection_args={
                        "host": get_config().MILVUS_HOST,
                        "port": get_config().MILVUS_PORT
                    },
                    vector_field="vector",
                    text_field="content"
                )
            elif self.db_type == "qdrant":
                from langchain_qdrant import QdrantVectorStore
                self._client = QdrantVectorStore.from_existing_collection(
                    embedding=self.embedding,
                    collection_name=self.collection_name,
                    url=f"http://{get_config().QDRANT_HOST}:{get_config().QDRANT_PORT}"
                )
            elif self.db_type == "pgvector":
                from langchain_postgres import PGVectorStore
                self._client = PGVectorStore.from_existing_table(
                    embedding=self.embedding,
                    table_name=self.collection_name,
                    connection_string=get_config().PGVECTOR_CONN
                )
            else:
                raise ValueError(f"Unsupported vector DB type: {self.db_type}")
        except ImportError as e:
            print(f"Vector DB driver not installed: {e}")
            logger.error(f"向量数据库驱动未安装: db_type={self.db_type}, error: {str(e)}")
            self._client = None
        except Exception as e:
            logger.error(f"初始化LangChain向量存储失败: db_type={self.db_type}, error: {str(e)}", exc_info=True)
            self._client = None

    @property
    def client(self):
        """获取底层客户端"""
        return self._client

    def add_texts(
        self,
        texts: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        **kwargs
    ) -> List[str]:
        """添加文本到向量存储"""
        if self._client is None:
            return []

        docs = [
            Document(page_content=text, metadata=meta or {})
            for text, meta in zip(texts, metadatas or [{}] * len(texts))
        ]

        if hasattr(self._client, "add_documents"):
            return self._client.add_documents(docs, ids=ids, **kwargs)
        return []

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Document]:
        """相似性搜索"""
        if self._client is None:
            return []
        return self._client.similarity_search(query, k=k, filter=filter, **kwargs)

    def similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Document]:
        """通过向量搜索"""
        if self._client is None:
            return []
        return self._client.similarity_search_by_vector(embedding, k=k, filter=filter, **kwargs)

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[tuple[Document, float]]:
        """带分数的相似性搜索"""
        if self._client is None:
            return []
        return self._client.similarity_search_with_score(query, k=k, filter=filter, **kwargs)

    def delete(self, ids: Optional[List[str]] = None, **kwargs) -> None:
        """删除向量"""
        if self._client and hasattr(self._client, "delete"):
            self._client.delete(ids=ids, **kwargs)

    def as_retriever(self, **kwargs) -> VectorStoreRetriever:
        """转换为 Retriever"""
        if self._client is None:
            return _MockRetriever()
        return self._client.as_retriever(**kwargs)


class _MockRetriever(VectorStoreRetriever):
    """当向量存储不可用时的 Mock Retriever"""

    def get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        return []

    async def aget_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        return []


def create_langchain_vectorstore(
    embedding,
    db_type: Optional[str] = None,
    collection_name: Optional[str] = None
) -> LangChainVectorStoreAdapter:
    """工厂函数：创建 LangChain VectorStore"""
    return LangChainVectorStoreAdapter(
        embedding=embedding,
        db_type=db_type,
        collection_name=collection_name
    )