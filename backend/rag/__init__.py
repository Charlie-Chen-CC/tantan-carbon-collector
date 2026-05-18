"""
RAG模块 - 碳管师收资系统
知识检索增强模块
接入阿里云通义千问LLM和向量数据库
"""

from .knowledge_base import CarbonKnowledgeBase, get_knowledge_base, RAGRetriever
from .retriever import RAGSearcher, RAGSearchResult, RAGPipeline, get_rag_searcher, get_rag_pipeline
from .ali_llm import AliLLMClient, AliEmbeddingClient, get_llm_client, get_embedding_client
from .vector_db import VectorDBClient, VectorDBFactory, get_vector_db_client

__all__ = [
    # 知识库
    "CarbonKnowledgeBase",
    "get_knowledge_base",
    "RAGRetriever",
    # 检索器
    "RAGSearcher",
    "RAGSearchResult",
    "RAGPipeline",
    "get_rag_searcher",
    "get_rag_pipeline",
    # 阿里云LLM
    "AliLLMClient",
    "AliEmbeddingClient",
    "get_llm_client",
    "get_embedding_client",
    # 向量数据库
    "VectorDBClient",
    "VectorDBFactory",
    "get_vector_db_client"
]
