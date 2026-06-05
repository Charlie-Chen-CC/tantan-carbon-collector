"""retriever.py RAGSearcher + RAGPipeline async 测试 (P0-2b)。

RAGSearcher.asearch + RAGPipeline.aanswer + RAGPipeline.aanswer_stream
"""
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from tantan.backend.rag.retriever import RAGSearcher, RAGPipeline, Document, RAGSearchResult


@pytest.mark.asyncio
async def test_rag_searcher_asearch_uses_async_kb():
    """RAGSearcher.asearch 应走 knowledge_base 适配器的 async 检索。"""
    searcher = RAGSearcher(knowledge_base=MagicMock())
    # 注入一个 mock vectorstore,提供 asimilarity_search_with_score
    mock_vs = MagicMock()
    mock_vs.asimilarity_search_with_score = AsyncMock(return_value=[
        (Document(page_content="c1", metadata={"chunk_id": "c1"}), 0.9)
    ])
    searcher._vectorstore = mock_vs

    results = await searcher.asearch("query", top_k=1)

    assert len(results) == 1
    assert results[0].score == 0.9
    assert results[0].content == "c1"
    mock_vs.asimilarity_search_with_score.assert_awaited_once_with("query", k=1)


@pytest.mark.asyncio
async def test_rag_searcher_asearch_propagates_errors():
    """RAGSearcher.asearch 内部异常应 propagate 到 async 端。"""
    searcher = RAGSearcher(knowledge_base=MagicMock())
    mock_vs = MagicMock()
    mock_vs.asimilarity_search_with_score = AsyncMock(
        side_effect=ConnectionError("kb down")
    )
    searcher._vectorstore = mock_vs

    with pytest.raises(ConnectionError, match="kb down"):
        await searcher.asearch("query")


@pytest.mark.asyncio
async def test_rag_pipeline_aanswer_calls_aachat():
    """RAGPipeline.aanswer 应 await llm_client.achat (P0-2a) + searcher.asearch。"""
    pipe = RAGPipeline(knowledge_base=MagicMock())
    pipe._llm_client = MagicMock()
    pipe._llm_client.achat = AsyncMock(return_value={
        "content": "answer text", "role": "assistant"
    })
    pipe._searcher = MagicMock()
    pipe._searcher.asearch = AsyncMock(return_value=[])

    result = await pipe.aanswer("question")

    assert result["answer"] == "answer text"
    assert result["question"] == "question"
    pipe._llm_client.achat.assert_awaited_once()
    pipe._searcher.asearch.assert_awaited_once_with("question", top_k=5)


@pytest.mark.asyncio
async def test_rag_pipeline_aanswer_returns_answer_with_sources():
    """RAGPipeline.aanswer 端到端返回 answer dict 含 sources。"""
    pipe = RAGPipeline(knowledge_base=MagicMock())
    pipe._llm_client = MagicMock()
    pipe._llm_client.achat = AsyncMock(return_value={
        "content": "final answer", "role": "assistant"
    })
    pipe._searcher = MagicMock()
    pipe._searcher.asearch = AsyncMock(return_value=[
        RAGSearchResult(chunk_id="c1", content="ref", metadata={"topic": "t", "source": "s"}, score=0.9)
    ])

    result = await pipe.aanswer("q", include_sources=True)

    assert result["answer"] == "final answer"
    assert "sources" in result
    assert result["sources"][0]["topic"] == "t"
    assert result["sources"][0]["source"] == "s"


@pytest.mark.asyncio
async def test_rag_pipeline_aanswer_stream_uses_achat_stream():
    """RAGPipeline.aanswer_stream 应 async-for 消费 llm_client.achat_stream。"""
    pipe = RAGPipeline(knowledge_base=MagicMock())
    pipe._llm_client = MagicMock()

    async def mock_stream(messages, **kwargs):
        yield {"content": "a", "role": "assistant"}
        yield {"content": "b", "role": "assistant"}
        yield {"content": "c", "role": "assistant"}
    pipe._llm_client.achat_stream = mock_stream
    pipe._searcher = MagicMock()
    pipe._searcher.asearch = AsyncMock(return_value=[])

    chunks = []
    async for chunk in pipe.aanswer_stream("q"):
        chunks.append(chunk)

    assert "".join(chunks) == "abc"
