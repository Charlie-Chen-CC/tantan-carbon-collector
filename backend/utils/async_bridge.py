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
