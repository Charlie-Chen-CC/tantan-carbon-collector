"""knowledge_base.py 4 个类加 async 方法测试 (P0-2b)。"""
import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from tantan.backend.rag.knowledge_base import (
    AliEmbeddingModel,
    VectorStore,
    RAGRetriever,
    CarbonKnowledgeBase,
)


@pytest.mark.asyncio
async def test_ali_embedding_model_aencode_calls_async_client():
    """AliEmbeddingModel.aencode 应 await embedding_client.aencode (P0-2a)。"""
    model = AliEmbeddingModel.__new__(AliEmbeddingModel)
    model.dimension = 1536
    model.embedding_client = MagicMock()
    model.embedding_client.aencode = AsyncMock(
        return_value={"embeddings": [[0.1, 0.2]], "dimension": 2}
    )

    result = await model.aencode(["hello"])

    assert result == [[0.1, 0.2]]
    model.embedding_client.aencode.assert_awaited_once_with(["hello"])


@pytest.mark.asyncio
async def test_vector_store_asearch_calls_async_db():
    """VectorStore.asearch 应 await vector_db_client.asearch。"""
    store = VectorStore.__new__(VectorStore)
    store.collection_name = "test"
    store.dimension = 1536
    store.vector_db_client = MagicMock()
    store.vector_db_client.asearch = AsyncMock(return_value=[{"id": "d1", "score": 0.9}])

    result = await store.asearch([0.1, 0.2], top_k=3)

    assert result == [{"id": "d1", "score": 0.9}]
    store.vector_db_client.asearch.assert_awaited_once_with("test", [0.1, 0.2], 3)


@pytest.mark.asyncio
async def test_vector_store_aadd_calls_async_db():
    """VectorStore.aadd 应 await vector_db_client.ainsert。"""
    store = VectorStore.__new__(VectorStore)
    store.collection_name = "test"
    store.dimension = 1536
    store.vector_db_client = MagicMock()
    store.vector_db_client.ainsert = AsyncMock(return_value=["id1"])

    result = await store.aadd("id1", [0.1], {"content": "c"})

    assert result is True
    store.vector_db_client.ainsert.assert_awaited_once_with(
        "test", [[0.1]], [{"content": "c"}], ["id1"]
    )


@pytest.mark.asyncio
async def test_rag_retriever_aretrieve_calls_async():
    """RAGRetriever.aretrieve 应 await embedding_model.aencode + vector_store.asearch。"""
    retriever = RAGRetriever.__new__(RAGRetriever)
    retriever.chunks = {}
    retriever._initialized = True
    retriever.embedding_model = MagicMock()
    retriever.embedding_model.aencode = AsyncMock(return_value=[[0.1, 0.2]])
    retriever.vector_store = MagicMock()
    retriever.vector_store.asearch = AsyncMock(return_value=[{"id": "d1", "score": 0.8}])

    result = await retriever.aretrieve("query", top_k=3)

    assert result == [{"id": "d1", "score": 0.8}]
    retriever.embedding_model.aencode.assert_awaited_once_with(["query"])
    retriever.vector_store.asearch.assert_awaited_once_with([0.1, 0.2], 3)


@pytest.mark.asyncio
async def test_rag_retriever_aadd_knowledge_calls_async():
    """RAGRetriever.aadd_knowledge 应 await 编码 + 添加。"""
    retriever = RAGRetriever.__new__(RAGRetriever)
    retriever.chunks = {}
    retriever._initialized = True
    retriever.embedding_model = MagicMock()
    retriever.embedding_model.aencode = AsyncMock(return_value=[[0.1]])
    retriever.vector_store = MagicMock()
    retriever.vector_store.aadd = AsyncMock(return_value=True)

    chunk_id = await retriever.aadd_knowledge("content", {"topic": "test"})

    assert isinstance(chunk_id, str)
    assert chunk_id in retriever.chunks
    retriever.embedding_model.aencode.assert_awaited_once_with(["content"])
    retriever.vector_store.aadd.assert_awaited_once()


@pytest.mark.asyncio
async def test_carbon_kb_aquery_calls_async():
    """CarbonKnowledgeBase.aquery 应 await retriever.aretrieve。"""
    kb = CarbonKnowledgeBase.__new__(CarbonKnowledgeBase)
    retriever = MagicMock()
    retriever.aretrieve = AsyncMock(return_value=[{"id": "d1"}])
    kb.retriever = retriever

    result = await kb.aquery("q", top_k=2)

    assert result == [{"id": "d1"}]
    retriever.aretrieve.assert_awaited_once_with("q", 2)


@pytest.mark.asyncio
async def test_carbon_kb_aquery_with_context_calls_async():
    """aquery_with_context 应用 section 增强后再 await 检索。"""
    kb = CarbonKnowledgeBase.__new__(CarbonKnowledgeBase)
    retriever = MagicMock()
    retriever.aretrieve = AsyncMock(return_value=[{
        "id": "d1", "content": "content", "metadata": {"topic": "topic"}
    }])
    kb.retriever = retriever

    result = await kb.aquery_with_context("q", context={"current_section": 1}, top_k=3)

    assert "topic" in result
    # 应传增强后的 query (含 section 1 关键字)
    call_args = retriever.aretrieve.await_args
    assert "q" in call_args.args[0]
    assert "企业" in call_args.args[0]
