"""VectorDBClient 3 个具体实现加 async 方法 (asearch/ainsert/adelete) 测试。

P0-2b: 全 asyncio.to_thread 包装同步方法 (用户决策, 匹配 P0-2a 模式)。
"""
import asyncio
import inspect
from unittest.mock import patch, MagicMock

import pytest

from tantan.backend.rag.vector_db import (
    MilvusClient,
    QdrantClient,
    PGVectorClient,
    VectorDBClient,
)


# ---------- MilvusClient async ----------

@pytest.mark.asyncio
async def test_milvus_asearch_calls_sync_search_via_to_thread():
    """asearch 应通过 asyncio.to_thread 调 sync search 返回 results。"""
    client = MilvusClient(host="x", port=1)
    client.connected = True

    with patch.object(client, "search", return_value=[{"id": "d1", "score": 0.9}]) as mock_search:
        result = await client.asearch("coll", [0.1, 0.2], top_k=3)

    assert result == [{"id": "d1", "score": 0.9}]
    mock_search.assert_called_once_with("coll", [0.1, 0.2], 3, None)


@pytest.mark.asyncio
async def test_milvus_ainsert_calls_sync_insert():
    """ainsert 应通过 asyncio.to_thread 调 sync insert。"""
    client = MilvusClient(host="x", port=1)
    client.connected = True
    with patch.object(client, "insert", return_value=["id1"]) as mock_insert:
        result = await client.ainsert("coll", [[0.1]], [{"content": "c"}], ["id1"])
    assert result == ["id1"]
    mock_insert.assert_called_once_with("coll", [[0.1]], [{"content": "c"}], ["id1"])


@pytest.mark.asyncio
async def test_milvus_adelete_calls_sync_delete():
    """adelete 应通过 asyncio.to_thread 调 sync delete。"""
    client = MilvusClient(host="x", port=1)
    client.connected = True
    with patch.object(client, "delete", return_value=True) as mock_delete:
        result = await client.adelete("coll", ["id1"])
    assert result is True
    mock_delete.assert_called_once_with("coll", ["id1"])


# ---------- QdrantClient async ----------

@pytest.mark.asyncio
async def test_qdrant_asearch_calls_sync_search_via_to_thread():
    """QdrantClient.asearch 应调 sync search。"""
    client = QdrantClient(host="x", port=1)
    client.connected = True
    with patch.object(client, "search", return_value=[{"id": "d1", "score": 0.8}]) as mock_search:
        result = await client.asearch("coll", [0.1], top_k=2)
    assert result == [{"id": "d1", "score": 0.8}]
    mock_search.assert_called_once_with("coll", [0.1], 2, None)


@pytest.mark.asyncio
async def test_qdrant_ainsert_calls_sync_insert():
    """QdrantClient.ainsert 应调 sync insert。"""
    client = QdrantClient(host="x", port=1)
    client.connected = True
    with patch.object(client, "insert", return_value=["id1"]) as mock_insert:
        result = await client.ainsert("coll", [[0.1]], [{"content": "c"}], ["id1"])
    assert result == ["id1"]
    mock_insert.assert_called_once_with("coll", [[0.1]], [{"content": "c"}], ["id1"])


@pytest.mark.asyncio
async def test_qdrant_adelete_calls_sync_delete():
    """QdrantClient.adelete 应调 sync delete。"""
    client = QdrantClient(host="x", port=1)
    client.connected = True
    with patch.object(client, "delete", return_value=True) as mock_delete:
        result = await client.adelete("coll", ["id1"])
    assert result is True
    mock_delete.assert_called_once_with("coll", ["id1"])


# ---------- PGVectorClient async ----------

@pytest.mark.asyncio
async def test_pgvector_asearch_calls_sync_search_via_to_thread():
    """PGVectorClient.asearch 应调 sync search。"""
    client = PGVectorClient(connection_string="postgresql://x")
    client.connected = True
    with patch.object(client, "search", return_value=[{"id": "d1", "score": 0.7}]) as mock_search:
        result = await client.asearch("coll", [0.1, 0.2], top_k=1)
    assert result == [{"id": "d1", "score": 0.7}]
    mock_search.assert_called_once_with("coll", [0.1, 0.2], 1, None)


@pytest.mark.asyncio
async def test_pgvector_ainsert_calls_sync_insert():
    """PGVectorClient.ainsert 应调 sync insert。"""
    client = PGVectorClient(connection_string="postgresql://x")
    client.connected = True
    with patch.object(client, "insert", return_value=["id1"]) as mock_insert:
        result = await client.ainsert("coll", [[0.1]], [{"content": "c"}], ["id1"])
    assert result == ["id1"]
    mock_insert.assert_called_once_with("coll", [[0.1]], [{"content": "c"}], ["id1"])


@pytest.mark.asyncio
async def test_pgvector_adelete_calls_sync_delete():
    """PGVectorClient.adelete 应调 sync delete。"""
    client = PGVectorClient(connection_string="postgresql://x")
    client.connected = True
    with patch.object(client, "delete", return_value=True) as mock_delete:
        result = await client.adelete("coll", ["id1"])
    assert result is True
    mock_delete.assert_called_once_with("coll", ["id1"])


# ---------- AST 守门 ----------

def test_all_async_methods_have_await_in_vector_db():
    """红线: vector_db.py 所有 async def 内部必须 await。

    防 P0-2c/d 后续 PR 把 async def 改回空 body (假异步)。
    """
    import ast

    src_file = inspect.getsourcefile(VectorDBClient)
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
            f"违反 P0-2b 红线 'async def 必有 await'"
        )
