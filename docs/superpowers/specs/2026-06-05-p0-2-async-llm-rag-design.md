# P0-2 LLM/RAG/Vector DB 异步化 — 设计稿

- **作者**: Claude Code (brainstorming skill)
- **日期**: 2026-06-05
- **范围**: `docs/CODE_REVIEW_2026-06-03.md` §四 4.3【同步 LLM 阻塞 event loop】+ §四 4.4【路由函数 async def 但内部 0 个 await】+ 4.7【batch SSE 根因】
- **关联 PR**: 计划拆 4 个子 P0（用户已确认）

## 1. 背景与 WHY

### 1.1 现状
当前 `tantan/backend/rag/ali_llm.py`、`backend/rag/vector_db.py`、`backend/agents/qa_agent.py`、5 个路由文件全部是**同步阻塞调用**。但 FastAPI 路由签名是 `async def`，导致：

1. **Event loop 阻塞**：dashscope `Generation.call` 平均 5-15s，期间整个 server 任何 IO 都被挂起
2. **SSE 假流式根因**（P0-4 已修表面但根没动）：`qa_agent.generate_response_stream` 是 **sync generator**，被 `chat_stream` 路由的 `async def event_generator()` 当 async 用——FastAPI 在 sync generator 第一次 yield 时才把整个 generator 跑完再 yield 出来，**SSE 流式本质是同步生成完再按事件切分**（详见下方 §5.3）
3. **测试不稳定**：sse_starlette `EventSourceResponse` 跨测试绑死 event loop（CLAUDE.md 已记录 workaround），根因也是 sync generator 跨 event loop 调度

### 1.2 不修的后果
- 高并发 SSE 场景下 P99 延迟 > 30s（单 LLM 调用卡住整个进程）
- 横向扩容时，**节点越多 → 同步阻塞越严重**（线程池被吃光）
- 真实流式承诺（P0-4 commit 写的"token-by-token"）在生产是谎言

### 1.3 用户红线（来自会话历史）
- ❌ 在已有同步方法上增加 `async def` 但不 `await`（假异步）
- ❌ 删 06-01 报告里"已修"项的代码
- ❌ 引入新依赖不更新 requirements.txt
- ❌ 用 `test.skip` 跳过测试作为"通过"
- ✅ 每次动代码必须更新 CLAUDE.md
- ✅ 每个 P0 一个 git 分支
- ✅ TDD：先写测试再实现

## 2. 总体策略：拆 4 个子 P0

按依赖顺序串行提交，每个独立分支、独立 PR、可独立 revert：

```
P0-2a (LLM async)  ──┐
                     ├──> P0-2c (QA Agent async + bridge helper) ──┐
P0-2b (Vector+RAG async) ──┘                                       │
                                                                     ├──> P0-2d (路由 await 链)
                                                                     ↓
                                                                  完成
```

| 子 P0 | 范围 | 风险 | 估计 diff | 依赖 |
|---|---|---|---|---|
| **P0-2a** | `ali_llm.py` 加 `async def achat/astream/aencode` | 低（纯加新方法） | +150 行 + 60 行测试 | 无 |
| **P0-2b** | `vector_db.py` 3 个 client + `retriever.py` + `knowledge_base.py` 加 async 方法 | 中（SDK 切换） | +250 行 + 100 行测试 | 无 |
| **P0-2c** | `qa_agent.py` 加 `async def agenerate_response(_stream)` + 共享 `bridge_sync_iter` helper | 中（解 SSE 假流式根） | +200 行 + 80 行测试 | 2a |
| **P0-2d** | 5 个 router `async def` 改用 `await` 调 async 入口 + 同步 SQL/Redis `to_thread` 包装 | 中（行为兼容） | +200 行 + 100 行测试 | 2a/2b/2c |

**总工作量**：~700 行实现 + ~340 行测试，4 个独立 commit、4 个独立 PR。

## 3. 包装策略：混合派

| 调用类型 | 包装方式 | 理由 |
|---|---|---|
| LLM `dashscope.Generation.call` | `asyncio.to_thread` | dashscope SDK 无 async 客户端，重写=巨大 scope；30s 调用接受 thread pool |
| LLM `dashscope.TextEmbedding.call` | `asyncio.to_thread` | 同上 |
| LLM 流式 `Generation.call(stream=True)` | **bridge 模式** (sync generator → async iterator) | 详见 §5.3 |
| Redis `redis.from_url().*` | `asyncio.to_thread` | sync redis-py 生态成熟；redislite 替换代价大 |
| SQLAlchemy `db.query()` | `asyncio.to_thread` | 同步 Session 改 AsyncSession 涉及全部 14 个 model + 9 个状态管理器，scope 失控；当前状态管理器用单 Session 模式，thread 隔离 OK |
| Milvus | `AsyncMilvusClient` (pymilvus 内置) | pymilvus 2.4+ 自带 async，零额外依赖 |
| Qdrant | `AsyncQdrantClient` (qdrant-client 内置) | qdrant-client 1.7+ 自带 async，零额外依赖 |
| PGVector | SQLAlchemy 2.0 `AsyncSession` + `asyncpg` | 唯一需要新依赖 `asyncpg`（**必须更新 requirements.txt**） |

## 4. 关键 helper：bridge_sync_iter

P0-2a (LLM 流式) 和 P0-2c (QA Agent 流式) 共用同一个 bridge 模式。**提到 `tantan/backend/utils/async_bridge.py`**，避免 2 处重复实现。

```python
# tantan/backend/utils/async_bridge.py
"""
Bridge 同步 generator / iterable → async iterator。

用途：把 dashscope stream、QA Agent sync stream 等同步生成器
无缝集成到 FastAPI async def 路由 / SSE / AsyncIterator 协议。
"""
import asyncio
import threading
from typing import AsyncIterator, Callable, Iterable, TypeVar

T = TypeVar("T")

async def bridge_sync_iter(
    sync_iter_factory: Callable[[], Iterable[T]],
) -> AsyncIterator[T]:
    """在后台线程跑 sync iterable，主协程通过 asyncio.Queue 异步消费。

    - sync_iter_factory: 每次调用返回一个新的 sync iterable（避免多消费者共享）
    - 异常会跨线程 propagate 到 async 端
    - 跨 event loop 安全：每次调用都新起线程 + 新 queue
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    DONE = object()

    def _run() -> None:
        try:
            for item in sync_iter_factory():
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except Exception as e:
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

**TDD**：先写 `test_async_bridge.py` 覆盖：正常 yield、异常 propagate、空 iter、跨 event loop 安全（用 `pytest.mark.asyncio` + `asyncio.new_event_loop()`）。

## 5. 各子 P0 详细设计

### 5.1 P0-2a LLM 客户端 async

**改动文件**：
- `backend/rag/ali_llm.py`：加 `async def achat / achat_stream / aencode / aencode_single`
- `backend/tests/backend/rag/test_ali_llm_async.py`（新建）

**签名约定**：
```python
class AliLLMClient:
    # 保留所有 sync 方法（向后兼容 P0-2c 之前的代码）
    def chat(self, messages, stream=False, **kwargs) -> Union[Dict, Iterator]: ...
    def generate(self, prompt, ...) -> Union[Dict, Iterator]: ...
    
    # 新增 async 方法
    async def achat(self, messages, **kwargs) -> Dict:
        """非流式 chat。内部 to_thread 调 self._sync_call。"""
        return await asyncio.to_thread(self._sync_call_only, self._build_kwargs(messages, stream=False, **kwargs))
    
    async def achat_stream(self, messages, **kwargs) -> AsyncIterator[Dict]:
        """流式 chat。bridge sync _stream_call → async iterator。"""
        kwargs = self._build_kwargs(messages, stream=True, **kwargs)
        async for chunk in bridge_sync_iter(lambda: self._stream_call(kwargs)):
            yield chunk
    
    async def aencode(self, texts, model=None) -> Dict:
        return await asyncio.to_thread(self._sync_encode, texts, model)
    
    async def aencode_single(self, text) -> List[float]:
        return await asyncio.to_thread(self._sync_encode_single, text)
```

**关键约束**：
- `async def` 内部必须有 `await`（用户红线）
- 不能简单 wrap `def chat` → `async def chat = asyncio.to_thread(self.chat, ...)`，因为 `chat(stream=True)` 返回 generator，要走 bridge
- 必须**保留 sync 方法**（不破坏 P0-2c 之前的调用方；qa_agent.py 在 P0-2c 之前继续用 sync）

**测试**：
- 4 cases：mock dashscope `Generation.call` 返回固定 dict，验证 `await achat()` 拿到结果
- 1 case：mock `Generation.call(stream=True)` 返回 yield，验证 `async for` 真的在跨 await 边界 yield（用 `asyncio.sleep(0)` 验证控制权归还）
- 1 case：`await asyncio.wait_for(achat(), timeout=2)` 验证非阻塞（mock `time.sleep(1)` 验证可被中断）

### 5.2 P0-2b 向量库 + RAG 检索 async

**改动文件**：
- `backend/rag/vector_db.py`：3 个 client 加 `async def` 方法族（`aconnect/asearch/ainsert/adelete/a...`）
- `backend/rag/retriever.py`：`RAGSearcher` 加 `async def asearch`、`RAGPipeline` 加 `async def aanswer/aanswer_stream`
- `backend/rag/knowledge_base.py`：`CarbonKnowledgeBase` 加 `async def aquery/aquery_with_context`，`RAGRetriever` 加 `async def aretrieve/aadd_knowledge`
- `backend/tests/backend/rag/test_vector_db_async.py`（新建）
- `backend/tests/backend/rag/test_retriever_async.py`（新建）
- `backend/requirements.txt`：**+1 个依赖** `asyncpg`（PGVector 异步用）

**关键决策**：
- **抽象基类 `VectorDBClient` 不动**（避免破坏 3 个实现）；只加 3 个具体 client 的 async 方法
- **保留 sync 方法**（向后兼容）
- **AsyncMilvusClient**（pymilvus 2.4+ 自带，无新依赖）
- **AsyncQdrantClient**（qdrant-client 1.7+ 自带，无新依赖）
- **PGVector async**：SQLAlchemy 2.0 + asyncpg 异步引擎，**仅这个引入新依赖**

**测试**：
- mock 3 个 async client（不真起 Milvus/Qdrant/pg），验证 `await asearch()` 走的是 `asyncpg` / `AsyncMilvusClient` / `AsyncQdrantClient`（用 `inspect.iscoroutinefunction` 守门）
- 验证 `RAGPipeline.aanswer()` 内部 `await asearch` + `await achat`（来自 2a，stub）
- 验证异常 propagate 路径

### 5.3 P0-2c QA Agent async（**解 SSE 假流式根**）

**改动文件**：
- `backend/agents/qa_agent.py`：加 `async def agenerate_response` / `agenerate_response_stream`
- `backend/utils/async_bridge.py`（P0-2a 已建，P0-2c 共用）
- `backend/tests/backend/agents/test_qa_agent_async.py`（新建）

**SSE 假流式根因（关键）**：

当前代码 `chat_stream` 路由：
```python
async def chat_stream(...):
    def event_generator():                        # ← sync generator
        for event in qa_agent.generate_response_stream(...):  # ← sync iterable
            yield sse.encode()                    # ← FastAPI 在 yield 时跑完整个 generator
    return StreamingResponse(event_generator(), ...)
```

FastAPI 收到 `StreamingResponse(sync_generator)` 时，**不是真异步消费**——它会跑 `__next__()` 拿下一个 chunk，而 `__next__()` 阻塞在 dashscope `Generation.call(stream=True)` 的网络 I/O 上，**期间 event loop 依然被卡**（P0-4 修的"假流式"是把 sync generator 切成 10 字符再 yield，看起来流了，实际还是先有整段响应）。

**修后**：
```python
async def chat_stream(...):
    qa_agent = QAAgent()
    qa_agent.set_session(session_id)
    
    async def event_generator():
        async for event in qa_agent.agenerate_response_stream(message, context):
            # event_generator 本身是 async generator，
            # FastAPI 用 AsyncIOBackend 真异步消费，
            # 中间靠 asyncio.to_thread 释放 event loop
            ...
            yield sse.encode()
    
    return StreamingResponse(event_generator(), ...)
```

`qa_agent.agenerate_response_stream` 内部用 `bridge_sync_iter` 把内部同步 `generate_response_stream` 桥到 async iterator。**这才是真正的 token-by-token 流式**——event loop 在每个 yield 之间都能切走。

**关键约束**：
- `async def` 必须 `await`（用户红线）
- 不能简单 `agenerate_response_stream = generate_response_stream`（那是 sync generator，违反类型契约）
- `chat_stream` 路由的 `event_generator` 必须**改成 `async def` + `async for`**（这是 P0-2d 的事，P0-2c 只动 qa_agent.py）

**测试**：
- mock `QAAgent.generate_response_stream`（sync）返回 yield 3 次
- 验证 `agenerate_response_stream` 真在 async 端 yield（用 `asyncio.gather` 并发跑两个 consumer 验证不死锁）
- 验证 mock 抛异常时 async 端 `raise` 而不是返回

### 5.4 P0-2d 路由 await 链 + 同步 SQL/Redis

**改动文件**：
- `backend/api/chat_router.py`：3 个 `async def` 改用 `await`
- `backend/api/form_router.py`：4 个 `async def` 改用 `await`
- `backend/api/sessions_router.py`：3 个 `async def` 改用 `await`
- `backend/api/history_router.py`：1 个 `async def` 改用 `await`
- `backend/api/auth.py`：7 个 `async def` 改用 `await`（调 `await aget_redis_client` / `await aredis_op`）
- `backend/state/database_manager.py`：**`to_thread` 包装核心方法**（`get_session` / `save_form_data` / `add_history` / `get_form_data`）
- `backend/tests/backend/api/test_router_async_await.py`（新建）
- `backend/tests/backend/api/test_auth_redis_async.py`（新建）
- `backend/e2e/test_api_concurrent_sse.py`（新建，端到端：2 个 SSE 并发，验证都不被对方阻塞）

**关键约束**：
- **不动** `main.py:125-145` 的 `exception_handler`（用户红线）
- 每个 `async def` 内部**至少 1 个 `await`**（守门测试）
- 同步 SQL 全部用 `await asyncio.to_thread(state_manager.X, ...)` 包装
- 同步 Redis 全部用 `await asyncio.to_thread(redis_client.X, ...)` 包装
- `DatabaseStateManager` 的方法**保留 sync 签名**（给 P0-2d 之外的脚本用），P0-2d 在调用方 `to_thread`

**测试**：
- **AST 守门**（`test_router_async_await.py`）：扫所有 `async def` 函数，断言其内部 `await` 次数 ≥ 1
- **行为测试**：`httpx.AsyncClient` 打 `/api/chat`、`/api/form/...` 验证响应与 P0-2d 之前一致
- **并发测试**：用 `asyncio.gather` 并发跑 2 个 `POST /api/chat/stream`（mock 掉 dashscope），验证其中一个卡住时另一个能正常 yield（事件循环没死锁）
- **回归**：`backend/tests` 全套 193+ 测试全过

## 6. 4 个独立 commit 计划

```
commit 1 (P0-2a): "feat(backend/rag): AliLLMClient 加 achat/astream async 入口（解 LLM 阻塞 event loop）"
commit 2 (P0-2b): "feat(backend/rag): VectorDB 3 client + RAGSearcher 加 async 方法（解向量检索阻塞）"
commit 3 (P0-2c): "feat(backend/agents): QAAgent 加 agenerate_response(_stream)（解 SSE 假流式根因）"
commit 4 (P0-2d): "feat(backend/api): 5 路由 await 链 + 同步 SQL/Redis to_thread（解 11 个假异步路由）"
```

每个 commit 单独可 revert；串行合并后 = 完整 P0-2 修复。

## 7. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| `bridge_sync_iter` 跨 event loop 边界异常 | 2a/2c 测试 flaky | 每次调用新起 thread + queue，threading.Thread(daemon=True) |
| `to_thread` 默认 thread pool 8 个 | 10+ 并发阻塞 | 不在本期解决（YAGNI），生产再调 `loop.set_default_executor(ThreadPoolExecutor(max_workers=32))` |
| AsyncMilvus/AsyncQdrant API 与 sync 不完全一致 | 2b 行为漂移 | 守门测试对比 sync/async 返回值；不一致的地方加 adapter |
| PGVector 引入 asyncpg | 启动期多 1 个依赖 | requirements.txt 显式增 `asyncpg>=0.27`；docker 镜像加一层 |
| `to_thread` 跨线程共享 SQLAlchemy Session | 2d 状态管理器抛 `DetachedInstanceError` | `DatabaseStateManager` 在每个 `to_thread` 调用里**现场 `Session()`**，用完 `session.close()`；不缓存 Session 跨调用（现有 `state_manager` 已经是每方法开 Session 模式，符合） |
| 旧调用方仍用 sync 入口 | 双轨期混淆 | 旧方法**保留**，仅加 `_async` 后缀新方法；CLAUDE.md 明确"新代码必须用 async" |
| 4 个子 P0 串行合并冲突 | merge 时间长 | 每个 PR 都先 rebase master 再合；3-4 个 commit 之间无重叠文件 |

## 8. CLAUDE.md 必更新

按用户红线"动代码必更新 CLAUDE.md"，4 个 PR 每个都要更新：
- `backend/CLAUDE.md`：标注"LLM/Embedding/Redis/SQL 全部走 async；新代码禁止 sync 入口"
- `backend/rag/CLAUDE.md`：标注"AliLLMClient 既有 sync（向后兼容）又有 async（新代码必须 async）"
- `backend/agents/CLAUDE.md`：标注"QAAgent agenerate_response(_stream) 是真 async，stream 真的 token-by-token"
- `backend/api/CLAUDE.md`：标注"所有路由 async def 必须 await；禁止 async def 内无 await（守门测试已加）"
- 新建 `backend/utils/CLAUDE.md`：标注 `async_bridge.py` 是 P0-2a/2c 共享 helper

## 9. requirements.txt 必更新

**当前 requirements.txt 状态**（2026-06-05 扫）：`pymilvus` / `qdrant-client` **未列**（默认走 PGVector 路径）；PGVector async 需新依赖 `asyncpg`；测试需新依赖 `pytest-asyncio`（P0-2a/2c 跨 event loop 测试要用）。

按用户红线"❌ 引入新依赖不更新 requirements.txt"，P0-2b 提交时必须：
- `+ asyncpg>=0.27`（PGVector 异步用）
- `+ pymilvus>=2.4.0`（备用，AsyncMilvusClient 用；如果项目不切到 Milvus 可不列，但保留约束）
- `+ qdrant-client>=1.7.0`（备用，同上）
- `+ pytest-asyncio>=0.23`（P0-2a/2c 异步测试用）

**验证步骤**：4 个子 P0 提交前跑 `pip install -r backend/requirements.txt --dry-run` 确认依赖一致；CI 加 `pip check` 步骤。

## 10. 完成定义（Definition of Done）

每个子 P0 必须满足：
- [ ] AST 守门测试通过（async def 必有 await）
- [ ] 单元测试覆盖新增 async 方法
- [ ] 集成测试验证端到端不破坏 sync 调用方
- [ ] `backend/tests` 全套 193+ 测试全过
- [ ] 4 个相关 CLAUDE.md 已更新
- [ ] requirements.txt 已更新
- [ ] 独立 git 分支已推送远端
- [ ] PR 描述含 WHY / WHAT / TEST / 风险 4 节
- [ ] 现有 6 个 P0 PR 仍能正常 merge / rebase

4 个子 P0 全部完成后，**整个 P0-2 修复** = 4 个独立 commit + 4 个独立 PR + P0 进度表 13 项（10 → 14 项）。

## 11. 不在本期范围

为避免 scope 失控，明确**不做**的事：
- ❌ dashscope 替换为 httpx async 客户端
- ❌ SQLAlchemy 全量切到 `AsyncSession`（仅 PGVector 用）
- ❌ Celery / 后台任务队列（留给 P1）
- ❌ SSE 端点重写为原生 `EventSourceResponse`（sse_starlette 1.8+ 跨 event loop 已知问题，workaround 已用 `StreamingResponse(ServerSentEvent.encode())`）
- ❌ 数据库连接池调优（YAGNI）
- ❌ 性能 benchmark（用户没要求；做完所有子 P0 后跑 `wrk`/ab 验证并发即可）
