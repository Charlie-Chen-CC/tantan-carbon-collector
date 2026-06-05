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
