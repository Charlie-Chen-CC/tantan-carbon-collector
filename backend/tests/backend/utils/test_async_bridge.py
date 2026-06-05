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
