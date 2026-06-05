"""AliLLMClient / AliEmbeddingClient async 方法测试 + AST 守门。"""
import asyncio
import inspect
import time
from unittest.mock import patch, MagicMock

import pytest

from tantan.backend.rag.ali_llm import AliLLMClient, AliEmbeddingClient


# ---------- AliLLMClient.achat (非流式) ----------

@pytest.mark.asyncio
async def test_achat_returns_content_dict():
    """achat 应返回 sync chat 的结果 (dict 形式)。"""
    client = AliLLMClient(api_key="test-key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.output.choices = [MagicMock()]
    mock_response.output.choices[0].message = {"content": "hello"}

    with patch("dashscope.Generation.call", return_value=mock_response):
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

    assert result == {
        "content": "hello",
        "role": "assistant",
        "finish_reason": "stop",
    }


@pytest.mark.asyncio
async def test_achat_does_not_block_event_loop():
    """achat 内部走 to_thread, async 端能并发跑别的协程。"""
    client = AliLLMClient(api_key="test-key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.output.choices = [MagicMock()]
    mock_response.output.choices[0].message = {"content": "x"}

    def slow_call(*args, **kwargs):
        time.sleep(0.1)  # 模拟 sync 阻塞 100ms
        return mock_response

    async def other_coro():
        await asyncio.sleep(0.01)
        return "ok"

    with patch("dashscope.Generation.call", side_effect=slow_call):
        other_task = asyncio.create_task(other_coro())
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])
        other_result = await other_task

    assert result["content"] == "x"
    assert other_result == "ok"


@pytest.mark.asyncio
async def test_achat_propagates_dashscope_error():
    """dashscope 返回非 200 时 achat 应返回 error dict (不抛异常)。"""
    client = AliLLMClient(api_key="test-key")
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.message = "auth failed"

    with patch("dashscope.Generation.call", return_value=mock_response):
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

    assert "error" in result
    assert "401" in result["error"]


# ---------- AliLLMClient.achat_stream (流式) ----------

@pytest.mark.asyncio
async def test_achat_stream_yields_chunks():
    """achat_stream 应 async-iter 每个 chunk。"""
    client = AliLLMClient(api_key="test-key")
    chunk1 = MagicMock()
    chunk1.status_code = 200
    chunk1.output.choices = [MagicMock()]
    chunk1.output.choices[0].message = {"content": "a"}

    chunk2 = MagicMock()
    chunk2.status_code = 200
    chunk2.output.choices = [MagicMock()]
    chunk2.output.choices[0].message = {"content": "b"}

    with patch("dashscope.Generation.call", return_value=iter([chunk1, chunk2])):
        chunks = []
        async for chunk in client.achat_stream(
            messages=[{"role": "user", "content": "hi"}]
        ):
            chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0]["content"] == "a"
    assert chunks[1]["content"] == "b"


# ---------- AliEmbeddingClient.aencode / aencode_single ----------

@pytest.mark.asyncio
async def test_aencode_returns_embeddings_dict():
    """aencode 应返回 sync encode 的结果。"""
    client = AliEmbeddingClient(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.output = {"embeddings": [{"embedding": [0.1, 0.2, 0.3]}]}

    with patch("dashscope.TextEmbedding.call", return_value=mock_resp):
        result = await client.aencode(texts=["hello"])

    assert result["embeddings"] == [[0.1, 0.2, 0.3]]


@pytest.mark.asyncio
async def test_aencode_single_returns_vector():
    """aencode_single 应返回第一个 embedding 向量。"""
    client = AliEmbeddingClient(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.output = {"embeddings": [{"embedding": [0.4, 0.5]}]}

    with patch("dashscope.TextEmbedding.call", return_value=mock_resp):
        result = await client.aencode_single(text="hi")

    assert result == [0.4, 0.5]


# ---------- AST 守门: async def 内必须有 await ----------

def test_all_async_methods_have_await():
    """红线守门: AliLLMClient/AliEmbeddingClient 所有 async def 内部必须 await。

    防止 P0-2d 后续 PR 把 async def 改回空 body (假异步)。
    """
    import ast

    src_file = inspect.getsourcefile(AliLLMClient)
    assert src_file is not None
    with open(src_file, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        has_await = any(
            isinstance(child, (ast.Await, ast.AsyncFor, ast.AsyncWith))
            for child in ast.walk(node)
        )
        assert has_await, (
            f"async def {node.name} (line {node.lineno}) 内部无 await — "
            f"违反 P0-2a 红线 'async def 必有 await'"
        )
