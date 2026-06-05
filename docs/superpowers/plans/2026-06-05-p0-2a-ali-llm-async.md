# P0-2a AliLLMClient Async Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `AliLLMClient` / `AliEmbeddingClient` 加 async 方法 (`achat` / `achat_stream` / `aencode` / `aencode_single`)，让 FastAPI 路由能 `await` LLM 调用不阻塞 event loop。

**Architecture:** 保留所有 sync 方法 (向后兼容 P0-2c 之前的调用方)；新增 `a*` 方法：`asyncio.to_thread` 包装 sync 方法 (非流式)，`bridge_sync_iter` 包装 sync generator (流式)。共享 helper `bridge_sync_iter` 在 `tantan/backend/utils/async_bridge.py`，P0-2c 共用。

**Tech Stack:** Python 3.11+, asyncio, `asyncio.to_thread` (3.9+ stdlib), `pytest-asyncio` (新增依赖)

---

## File Structure

**新建文件**:
- `tantan/backend/utils/async_bridge.py` — `bridge_sync_iter` helper
- `tantan/backend/utils/CLAUDE.md` — utils 模块文档
- `tantan/backend/tests/backend/utils/test_async_bridge.py` — bridge 单测
- `tantan/backend/tests/backend/rag/test_ali_llm_async.py` — async LLM 单测 + AST 守门

**修改文件**:
- `tantan/backend/rag/ali_llm.py` — 加 4 个 async 方法 + 抽出 `_build_call_kwargs`
- `tantan/backend/rag/CLAUDE.md` — 文档化 async 入口
- `tantan/backend/tests/backend/CLAUDE.md` — 测试数 +11
- `tantan/backend/requirements.txt` — `+pytest-asyncio>=0.23`

**关键契约** (本 PR 必须满足):
- ✅ 旧 `chat` / `generate` / `encode` / `encode_single` sync 方法**完全保留** (P0-2a 之后才被 P0-2c 切)
- ✅ 新 async 方法**至少有 1 个 `await`** (红线, AST 守门测试强制)
- ✅ 异常跨线程 propagate (bridge_sync_iter 内部 `BaseException` 捕获 + 重 raise)

---

## Tasks

### Task 1: 添加 pytest-asyncio 依赖

**Files:**
- Modify: `tantan/backend/requirements.txt:51` (在 `# 日志（可选增强）` 块之后追加)

- [ ] **Step 1: 编辑 requirements.txt**

打开 `tantan/backend/requirements.txt`, 在第 51 行 (`colorlog>=6.8.0` 之后) 追加:

```text

# 异步测试（P0-2a 引入）
pytest-asyncio>=0.23
```

- [ ] **Step 2: 安装 + 验证**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
pip install 'pytest-asyncio>=0.23'
python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"
```

Expected: 打印版本号 (如 `0.23.0` 或更高)。

- [ ] **Step 3: 创建分支 + 提交**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git checkout master
git pull origin master
git checkout -b fix/phase1-p0-2a-ali-llm-async
git add backend/requirements.txt
git commit -m "chore(deps): 添加 pytest-asyncio 为 P0-2a 异步测试用"
```

---

### Task 2: 写 bridge_sync_iter 失败测试 (顺序 yield)

**Files:**
- Create: `tantan/backend/tests/backend/utils/test_async_bridge.py`

- [ ] **Step 1: 创建测试文件**

```python
"""bridge_sync_iter 单元测试。"""
import asyncio

import pytest

from tantan.backend.utils.async_bridge import bridge_sync_iter

pytestmark = pytest.mark.asyncio


async def test_bridge_yields_all_items_in_order():
    """同步 iterable 的每个 item 按序 yield 到 async 端。"""
    items = []
    async for item in bridge_sync_iter(lambda: iter([1, 2, 3])):
        items.append(item)
    assert items == [1, 2, 3]
```

- [ ] **Step 2: 运行测试, 确认 RED**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests/backend/utils/test_async_bridge.py -v
```

Expected: `ImportError: cannot import name 'bridge_sync_iter' from 'tantan.backend.utils.async_bridge'` (module 不存在)。

- [ ] **Step 3: 提交 (red test)**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git add backend/tests/backend/utils/test_async_bridge.py
git commit -m "test(utils): bridge_sync_iter 顺序 yield 测试 (RED)"
```

---

### Task 3: 实现 bridge_sync_iter (GREEN)

**Files:**
- Create: `tantan/backend/utils/async_bridge.py`

- [ ] **Step 1: 创建 async_bridge.py**

```python
"""同步 iterable → async iterator 桥接器。

P0-2a (LLM async) 和 P0-2c (QA Agent async) 共用此 helper。
把同步生成器 (dashscope stream、QAAgent.generate_response_stream 等)
集成到 FastAPI async def 路由 / SSE 协议。
"""
import asyncio
import threading
from typing import AsyncIterator, Callable, Iterable, TypeVar

T = TypeVar("T")


async def bridge_sync_iter(
    sync_iter_factory: Callable[[], Iterable[T]],
) -> AsyncIterator[T]:
    """在后台线程跑 sync iterable, 主协程通过 asyncio.Queue 异步消费。

    Args:
        sync_iter_factory: 每次调用返回新 sync iterable 的 factory。
            必须是 factory 不是 iterable 本身——避免多消费者共享同一迭代器。

    Yields:
        iterable 中的每个 item (按 sync 端顺序)。

    Raises:
        BaseException: sync iterable 抛出的任何异常会跨线程 propagate
        到 async 端 (包括 KeyboardInterrupt / SystemExit)。
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    DONE = object()

    def _run() -> None:
        try:
            for item in sync_iter_factory():
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except BaseException as e:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, e)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, DONE)

    threading.Thread(target=_run, daemon=True).start()

    while True:
        item = await queue.get()
        if item is DONE:
            return
        if isinstance(item, BaseException):
            raise item
        yield item
```

- [ ] **Step 2: 运行测试, 确认 GREEN**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests/backend/utils/test_async_bridge.py -v
```

Expected: `1 passed`。

- [ ] **Step 3: 提交 (green implementation)**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git add backend/utils/async_bridge.py
git commit -m "feat(utils): bridge_sync_iter 同步 iterable→async iterator 桥接器"
```

---

### Task 4: 补充 bridge 测试 (异常/空/并发)

**Files:**
- Modify: `tantan/backend/tests/backend/utils/test_async_bridge.py:9-20` (追加 3 个测试)

- [ ] **Step 1: 追加 3 个测试**

在文件末尾追加:

```python


async def test_bridge_propagates_exception():
    """sync iterable 抛异常时, async 端应 raise (不静默吞)。"""
    def factory():
        def gen():
            yield "a"
            raise ValueError("boom")
        return gen()

    with pytest.raises(ValueError, match="boom"):
        async for _ in bridge_sync_iter(factory):
            pass


async def test_bridge_handles_empty_iterable():
    """空 iterable 不死循环, 正常返回。"""
    items = []
    async for item in bridge_sync_iter(lambda: iter([])):
        items.append(item)
    assert items == []


async def test_bridge_releases_event_loop():
    """bridge 后台跑 thread, async 端 await queue.get() 应能并发跑别的协程。"""
    import time

    def slow_factory():
        for i in range(3):
            time.sleep(0.05)  # 模拟 sync 阻塞 50ms
            yield i

    async def other_coro():
        await asyncio.sleep(0.01)
        return "other-done"

    other_task = asyncio.create_task(other_coro())
    items = []
    async for item in bridge_sync_iter(slow_factory):
        items.append(item)
    other_result = await other_task

    assert items == [0, 1, 2]
    assert other_result == "other-done"
```

- [ ] **Step 2: 运行所有 bridge 测试**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests/backend/utils/test_async_bridge.py -v
```

Expected: `4 passed`。

- [ ] **Step 3: 提交**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git add backend/tests/backend/utils/test_async_bridge.py
git commit -m "test(utils): bridge 异常/空/并发场景覆盖"
```

---

### Task 5: 重构 ali_llm.py 抽出 `_build_call_kwargs`

**Files:**
- Modify: `tantan/backend/rag/ali_llm.py:26-55` (替换 `_call` 方法)

- [ ] **Step 1: 重构 `_call` 方法**

打开 `tantan/backend/rag/ali_llm.py`. 找到现有 `_call` 方法 (第 26-55 行), 替换为:

```python
    def _build_call_kwargs(
        self,
        messages: List[Dict[str, str]],
        stream: bool,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        """内部: 构造 dashscope Generation.call 的 kwargs。

        P0-2a 重构: 从原 _call 抽出, async 方法 (achat/achat_stream) 复用。
        """
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
            "result_format": "message",
        }
        if stream:
            kwargs["stream"] = True
        if temperature is not None:
            kwargs["temperature"] = temperature
        else:
            kwargs["temperature"] = self.temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = self.max_tokens
        return kwargs

    def _call(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        """内部: 调用 dashscope Generation.call。"""
        from dashscope import Generation

        kwargs = self._build_call_kwargs(messages, stream, temperature, max_tokens)

        if stream:
            return self._stream_call(kwargs)
        return self._sync_call(kwargs)
```

- [ ] **Step 2: 验证向后兼容 (现有 rag 测试仍过)**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests/backend/rag/ -v
```

Expected: 所有现有 rag 测试 pass。如有失败, revert Step 1。

- [ ] **Step 3: 提交**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git add backend/rag/ali_llm.py
git commit -m "refactor(rag): ali_llm 抽出 _build_call_kwargs 供 async 方法复用"
```

---

### Task 6: 写 AliLLMClient async 失败测试 (7 cases)

**Files:**
- Create: `tantan/backend/tests/backend/rag/test_ali_llm_async.py`

- [ ] **Step 1: 创建测试文件**

```python
"""AliLLMClient / AliEmbeddingClient async 方法测试 + AST 守门。"""
import asyncio
import inspect
import time
from unittest.mock import patch, MagicMock

import pytest

from tantan.backend.rag.ali_llm import AliLLMClient, AliEmbeddingClient

pytestmark = pytest.mark.asyncio


# ---------- AliLLMClient.achat (非流式) ----------

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

async def test_aencode_returns_embeddings_dict():
    """aencode 应返回 sync encode 的结果。"""
    client = AliEmbeddingClient(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.output = {"embeddings": [{"embedding": [0.1, 0.2, 0.3]}]}

    with patch("dashscope.TextEmbedding.call", return_value=mock_resp):
        result = await client.aencode(texts=["hello"])

    assert result["embeddings"] == [[0.1, 0.2, 0.3]]


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
```

- [ ] **Step 2: 运行测试, 确认全部 RED**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests/backend/rag/test_ali_llm_async.py -v
```

Expected: 7 个失败 (AttributeError: 'AliLLMClient' object has no attribute 'achat' 等)。

- [ ] **Step 3: 提交 (red tests)**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git add backend/tests/backend/rag/test_ali_llm_async.py
git commit -m "test(rag): AliLLMClient/EmbeddingClient async 方法守门测试 (RED)"
```

---

### Task 7: 实现 AliLLMClient.achat / achat_stream

**Files:**
- Modify: `tantan/backend/rag/ali_llm.py:1-13` (imports) + `:114-119` (新增方法)

- [ ] **Step 1: 添加 `asyncio` 和 `AsyncIterator` import**

打开 `tantan/backend/rag/ali_llm.py`. 找到顶部 imports (第 1-13 行), 替换为:

```python
"""
阿里云 DashScope LLM/Embedding 客户端 - 碳管师收资系统
Phase 2.6: 直接用 dashscope SDK, 不再走 LangChain 三层包装。

P0-2a (2026-06): 新增 async 方法 (achat / achat_stream / aencode / aencode_single)
解 FastAPI 路由同步阻塞 event loop 问题。
"""
import asyncio
import json
from typing import Dict, Any, Optional, List, Iterator, Union, AsyncIterator

from tantan.backend.config import get_config
from tantan.backend.utils import get_logger
from tantan.backend.utils.async_bridge import bridge_sync_iter

logger = get_logger(__name__)
```

- [ ] **Step 2: 在 `chat` 方法之后新增 `achat` / `achat_stream`**

找到 `chat` 方法 (第 102-114 行, 紧跟 `generate` 之后), 在 `count_tokens` 之前**整个插入**以下 2 个新方法:

```python
    async def achat(
        self,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> Dict[str, Any]:
        """异步非流式 chat。内部 to_thread 调 self.chat (stream=False)。"""
        return await asyncio.to_thread(self.chat, messages, stream=False, **kwargs)

    async def achat_stream(
        self,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """异步流式 chat。bridge sync _stream_call → async iterator。

        用 utils.async_bridge.bridge_sync_iter 把 dashscope sync generator
        桥到 async iterator, 让 FastAPI SSE 路由能真正异步消费。
        """
        def _make_iter():
            return self.chat(messages, stream=True, **kwargs)

        async for chunk in bridge_sync_iter(_make_iter):
            yield chunk
```

- [ ] **Step 3: 运行测试, 确认 4 个 LLM 测试 GREEN**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests/backend/rag/test_ali_llm_async.py -v
```

Expected: `4 passed, 3 failed` (LLM 通过, Embedding 还没实现, AST 守门待验证)。

- [ ] **Step 4: 提交**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git add backend/rag/ali_llm.py
git commit -m "feat(rag): AliLLMClient.achat/achat_stream async 入口 (P0-2a)"
```

---

### Task 8: 实现 AliEmbeddingClient.aencode / aencode_single

**Files:**
- Modify: `tantan/backend/rag/ali_llm.py:153-157` (新增方法)

- [ ] **Step 1: 在 `encode_single` 之后新增 async 方法**

找到 `encode_single` 方法 (第 153-157 行), 在其后追加:

```python
    async def aencode(self, texts: List[str], model: Optional[str] = None) -> Dict[str, Any]:
        """异步批量文本嵌入。

        Returns:
            与 sync `encode` 同结构。失败时 `{"embeddings": [], "error": "..."}`。
        """
        def _sync():
            from dashscope import TextEmbedding
            try:
                resp = TextEmbedding.call(
                    model=model or self.model,
                    input=texts,
                    api_key=self.api_key,
                )
                if resp.status_code == 200:
                    embeddings = [item["embedding"] for item in resp.output["embeddings"]]
                    return {
                        "embeddings": embeddings,
                        "model": model or self.model,
                        "dimension": len(embeddings[0]) if embeddings else 0,
                    }
                return {"embeddings": [], "error": f"status {resp.status_code}: {resp.message}"}
            except Exception as e:
                logger.error(f"dashscope TextEmbedding 失败: {e}", exc_info=True)
                return {"embeddings": [], "error": str(e)}

        return await asyncio.to_thread(_sync)

    async def aencode_single(self, text: str) -> List[float]:
        """异步单个文本嵌入。"""
        result = await self.aencode([text])
        emb = result.get("embeddings", [])
        return emb[0] if emb else []
```

- [ ] **Step 2: 运行所有 ali_llm 测试, 确认 7/7 GREEN**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests/backend/rag/test_ali_llm_async.py -v
```

Expected: `7 passed`。

- [ ] **Step 3: 提交**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git add backend/rag/ali_llm.py
git commit -m "feat(rag): AliEmbeddingClient.aencode/aencode_single async 入口"
```

---

### Task 9: 更新 CLAUDE.md 文档 (用户红线)

**Files:**
- Modify: `tantan/backend/rag/CLAUDE.md:11-15` (LLM 客户端段)
- Create: `tantan/backend/utils/CLAUDE.md`
- Modify: `tantan/backend/tests/backend/CLAUDE.md` (测试数)

- [ ] **Step 1: 编辑 backend/rag/CLAUDE.md**

找到 `### LLM 客户端（直接调 dashscope SDK）` 段, 在 `AliEmbeddingClient - 文本嵌入` 之后, 工厂函数之前, **插入**新段:

```markdown
**P0-2a 异步入口（2026-06 新增, 推荐新代码使用）**：
- `AliLLMClient.achat(messages, **kwargs)` - 异步非流式 chat, `asyncio.to_thread` 包装
- `AliLLMClient.achat_stream(messages, **kwargs)` - 异步流式 chat, 通过 `bridge_sync_iter` 桥接 sync generator
- `AliEmbeddingClient.aencode(texts, model=None)` - 异步批量嵌入
- `AliEmbeddingClient.aencode_single(text)` - 异步单文本嵌入
- **新旧并存**: 旧 `chat` / `generate` / `encode` / `encode_single` sync 方法**保留** (向后兼容 P0-2c 之前的调用方)
- **红线**: async def 内部必有 `await` (AST 守门测试 `test_all_async_methods_have_await` 强制)
```

- [ ] **Step 2: 创建 backend/utils/CLAUDE.md**

```markdown
# Utils - 工具模块

通用 helper 函数。

## 关键组件

### `async_bridge.py`（P0-2a 新建）
- `bridge_sync_iter(sync_iter_factory)` - 同步 iterable → async iterator 桥接器
- 用途: 把 dashscope stream、QA Agent sync stream 等同步生成器无缝集成到 FastAPI async def 路由 / SSE 协议
- 实现: 后台线程跑 sync iterable, 主协程通过 `asyncio.Queue` 异步消费
- 异常: sync iterable 抛出的任何 `BaseException` 会跨线程 propagate 到 async 端
- 共用者: P0-2a (LLM async) + P0-2c (QA Agent async)
```

- [ ] **Step 3: 更新 backend/tests/backend/CLAUDE.md 测试数**

打开 `tantan/backend/tests/backend/CLAUDE.md`, 找到 "测试数" 或 "Tests" 相关段, 追加 (或修改) 为:

```markdown
## 测试统计

- 2026-06-03: 189 测试
- P0-1 增量: +4 → 193
- **P0-2a 增量: +11 (4 bridge + 7 ali_llm async) → 204**
```

如果 CLAUDE.md 没有"测试统计"段, 仅追加上述 markdown 到文件末尾即可。

- [ ] **Step 4: 提交**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git add backend/rag/CLAUDE.md backend/utils/CLAUDE.md backend/tests/backend/CLAUDE.md
git commit -m "docs(backend): P0-2a async LLM 入口 + bridge helper 文档"
```

---

### Task 10: 全量回归 + smoke test

**Files:** 无 (验证)

- [ ] **Step 1: 全量 backend 测试**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -m pytest tantan/backend/tests --tb=short
```

Expected: 全部 pass, 总数 = 之前 + 11 (4 bridge + 7 ali_llm)。

如有失败:
- 读失败 test
- 判断是 P0-2a 引入还是 pre-existing
- P0-2a 引入: 在当前分支修
- pre-existing: 不在 P0-2a 范围, 在 PR 描述里标注 "pre-existing, unrelated"

- [ ] **Step 2: Import smoke test**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -c "
from tantan.backend.rag.ali_llm import AliLLMClient, AliEmbeddingClient
from tantan.backend.utils.async_bridge import bridge_sync_iter
import asyncio
print('AliLLMClient.achat:', asyncio.iscoroutinefunction(AliLLMClient.achat))
print('AliLLMClient.achat_stream:', asyncio.iscoroutinefunction(AliLLMClient.achat_stream))
print('AliEmbeddingClient.aencode:', asyncio.iscoroutinefunction(AliEmbeddingClient.aencode))
print('AliEmbeddingClient.aencode_single:', asyncio.iscoroutinefunction(AliEmbeddingClient.aencode_single))
print('bridge_sync_iter: imported OK')
"
```

Expected:
```
AliLLMClient.achat: True
AliLLMClient.achat_stream: True
AliEmbeddingClient.aencode: True
AliEmbeddingClient.aencode_single: True
bridge_sync_iter: imported OK
```

- [ ] **Step 3: 同步方法向后兼容 smoke test**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace
source tantan/backend/.venv/Scripts/activate
python -c "
from tantan.backend.rag.ali_llm import AliLLMClient, AliEmbeddingClient
import inspect
# 旧 sync 方法必须仍存在 (P0-2a 红线: 不删 P0-2c 之前依赖的 API)
for name in ['chat', 'generate', 'count_tokens']:
    method = getattr(AliLLMClient, name)
    assert not asyncio.iscoroutinefunction(method), f'{name} should be sync'
    print(f'AliLLMClient.{name}: sync OK')
for name in ['encode', 'encode_single']:
    method = getattr(AliEmbeddingClient, name)
    assert not asyncio.iscoroutinefunction(method), f'{name} should be sync'
    print(f'AliEmbeddingClient.{name}: sync OK')
"
```

Expected: 5 行 `... sync OK`。

- [ ] **Step 4: 如果 Step 1 修过代码, 追加 fix commit**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git status  # 应有修改
git add -u
git commit -m "fix(rag): P0-2a 全量回归修复"
```

如 Step 1 无修改, 跳过本步。

---

### Task 11: 推分支 + 创建 PR

**Files:** 无

- [ ] **Step 1: 检查 working tree 干净**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git status
```

Expected: `nothing to commit, working tree clean`。

- [ ] **Step 2: 推分支到 origin**

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
git push -u origin fix/phase1-p0-2a-ali-llm-async
```

Expected: `branch set up to track; new branch pushed`。

- [ ] **Step 3: 写 PR body 并创建 PR**

创建 `tantan/.pr-bodies/p0-2a-ali-llm-async.md`:

```markdown
## 背景

`docs/CODE_REVIEW_2026-06-03.md` §四 4.3【同步 LLM 阻塞 event loop】P0-2 拆 4 个子 P0 的第 1 个：仅动 LLM 客户端层。

## WHY

- 当前 `AliLLMClient.chat()` / `AliEmbeddingClient.encode()` 全是 sync `def`
- FastAPI 路由 `async def` 调 sync 方法 → 整个 event loop 被 dashscope HTTP 调用阻塞 5-15s
- 高并发 SSE 场景下 P99 延迟 > 30s

## WHAT

### 新建 `tantan/backend/utils/async_bridge.py`
- `bridge_sync_iter(sync_iter_factory)` 桥接 sync iterable → async iterator
- 后台线程跑 sync iter, 主协程通过 `asyncio.Queue` 异步消费
- 异常跨线程 propagate
- P0-2c 共用此 helper (QA Agent stream)

### `ali_llm.py` 新增 4 个 async 方法
- `AliLLMClient.achat(messages, **kwargs)` - `asyncio.to_thread(self.chat, stream=False)`
- `AliLLMClient.achat_stream(messages, **kwargs)` - `bridge_sync_iter(lambda: self.chat(stream=True))`
- `AliEmbeddingClient.aencode(texts, model=None)` - `asyncio.to_thread(...)`
- `AliEmbeddingClient.aencode_single(text)` - 包装 `aencode`

### 重构 `_call` 抽出 `_build_call_kwargs`
- 纯内部重构, 行为不变, 给 async 方法复用
- 现有 sync `chat` / `generate` / `encode` / `encode_single` **完全保留** (向后兼容 P0-2c 之前的调用方)

## TEST

- **4** bridge_sync_iter 测试 (顺序 yield / 异常 / 空 / 并发释放 event loop)
- **7** AliLLMClient/EmbeddingClient async 测试
  - 3 non-stream (返回 dict / 不阻塞 / 错误传播)
  - 1 stream (yield chunks)
  - 2 embedding (aencode / aencode_single)
  - 1 AST 守门 (async def 必有 await — 红线)
- **204/204** 后端回归通过 (193 + 11)

## 涉及文件

```
backend/utils/async_bridge.py                  (新建)
backend/utils/CLAUDE.md                       (新建)
backend/rag/ali_llm.py                         (改: +4 async 方法, 抽 _build_call_kwargs)
backend/rag/CLAUDE.md                          (改: 文档化 async 入口)
backend/requirements.txt                       (改: +pytest-asyncio>=0.23)
backend/tests/backend/utils/test_async_bridge.py    (新建)
backend/tests/backend/rag/test_ali_llm_async.py     (新建)
backend/tests/backend/CLAUDE.md                (改: 测试数 193 → 204)
```

## 风险

- **零行为变化**: 所有 sync 方法保留, 旧调用方不受影响
- **红线遵守**: AST 守门测试 `test_all_async_methods_have_await` 强制 async def 有 await
- **依赖新增**: `pytest-asyncio>=0.23` (test-only, 已在 requirements.txt)
- **后续 P0**: P0-2c (QA Agent) + P0-2d (路由) 会切到这些 async 入口

## 关联

- 设计稿: `docs/superpowers/specs/2026-06-05-p0-2-async-llm-rag-design.md` §5.1
- Review 报告: `docs/CODE_REVIEW_2026-06-03.md` §四 4.3
- 后续: P0-2b (Vector+RAG) / P0-2c (QA Agent) / P0-2d (路由)
```

创建 PR:

```bash
cd /c/Users/25776/Desktop/work/claude_workspace/tantan/tantan
gh pr create \
  --repo Charlie-Chen-CC/tantan-carbon-collector \
  --base master \
  --head fix/phase1-p0-2a-ali-llm-async \
  --title "P0-2a: AliLLMClient 加 achat/astream async 入口（解 LLM 阻塞 event loop）" \
  --body-file .pr-bodies/p0-2a-ali-llm-async.md
```

- [ ] **Step 4: 验证 PR URL**

Expected: gh 输出包含 `https://github.com/Charlie-Chen-CC/tantan-carbon-collector/pull/N` 形式的 URL。

---

## Self-Review

1. **Spec 覆盖**:
   - §5.1 `achat` / `achat_stream` / `aencode` / `aencode_single` → Task 6/7/8
   - §4 `bridge_sync_iter` helper → Task 2/3/4
   - 红线 (async def 必有 await) → Task 6 step 1 (AST 守门)
   - 保留 sync 方法 (向后兼容) → Task 5 重构不动 sync + Task 10 step 3 smoke test
   - requirements.txt 必更新 → Task 1
   - CLAUDE.md 必更新 → Task 9
   - 一 P0 一 git 分支 → Task 11 (`fix/phase1-p0-2a-ali-llm-async`)

2. **Placeholder 扫描**: 无 TBD/TODO/占位符, 所有 step 含完整代码或命令。

3. **类型一致**:
   - `achat` / `achat_stream` / `aencode` / `aencode_single` 命名跨 Task 6/7/8 一致
   - `bridge_sync_iter` 命名跨 Task 3/4/7 一致
   - `asyncio.to_thread` 用法跨 Task 7/8 一致

## 不在本 PR 范围 (per spec §11)

- httpx async client 替换 dashscope → 留 P1
- RAGSearcher / CarbonKnowledgeBase async → P0-2b
- QAAgent async → P0-2c
- 路由 await 链 → P0-2d
- 同步 SQL/Redis to_thread → P0-2d
