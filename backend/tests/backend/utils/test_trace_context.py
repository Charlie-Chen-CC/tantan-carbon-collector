"""
TraceContext 单元测试 - Phase 5.4 切到 contextvars

关键断言：
- TraceContext.get_trace_id 默认 None
- set_trace_id 写入后能读到
- set_trace_id 返回 Token，reset(token) 恢复原值
- 嵌套 set/reset 栈式还原
- 跨 asyncio.create_task 传播（contextvars 与 Task 一起拷贝）
- clear() 把当前值清回 None
"""
import asyncio

from tantan.backend.utils.logger import TraceContext, get_trace_id


class TestTraceContextBasics:
    """基本读写"""

    def test_default_none(self):
        assert TraceContext.get_trace_id() is None

    def test_set_get(self):
        token = TraceContext.set_trace_id("req-1")
        try:
            assert TraceContext.get_trace_id() == "req-1"
        finally:
            TraceContext.reset(token)

    def test_clear(self):
        token = TraceContext.set_trace_id("req-1")
        try:
            assert TraceContext.get_trace_id() == "req-1"
            TraceContext.clear()
            assert TraceContext.get_trace_id() is None
        finally:
            TraceContext.reset(token)

    def test_get_trace_id_module_helper(self):
        token = TraceContext.set_trace_id("req-2")
        try:
            assert get_trace_id() == "req-2"
        finally:
            TraceContext.reset(token)


class TestTraceContextTokenReset:
    """Token-based reset（Phase 5.4 重点）"""

    def test_reset_restores_none(self):
        assert TraceContext.get_trace_id() is None
        token = TraceContext.set_trace_id("req-x")
        assert TraceContext.get_trace_id() == "req-x"
        TraceContext.reset(token)
        assert TraceContext.get_trace_id() is None

    def test_nested_set_reset_stack(self):
        """set 嵌套 + reset 应 LIFO 还原"""
        assert TraceContext.get_trace_id() is None
        t1 = TraceContext.set_trace_id("outer")
        assert TraceContext.get_trace_id() == "outer"
        t2 = TraceContext.set_trace_id("inner")
        assert TraceContext.get_trace_id() == "inner"
        TraceContext.reset(t2)
        assert TraceContext.get_trace_id() == "outer"
        TraceContext.reset(t1)
        assert TraceContext.get_trace_id() is None

    def test_reset_does_not_leak_to_next_test(self):
        """异常路径下 reset 必须被调用 - 模拟请求异常后 try/finally 模式"""
        assert TraceContext.get_trace_id() is None
        token = TraceContext.set_trace_id("req-leak")
        try:
            try:
                raise RuntimeError("simulated")
            except RuntimeError:
                pass
        finally:
            TraceContext.reset(token)
        assert TraceContext.get_trace_id() is None


class TestTraceContextAsyncPropagation:
    """async 跨 Task 传播 - contextvars vs threading.local 的关键差异"""

    def test_propagates_to_create_task(self):
        async def child():
            return TraceContext.get_trace_id()

        async def parent():
            token = TraceContext.set_trace_id("req-async")
            try:
                return await asyncio.create_task(child())
            finally:
                TraceContext.reset(token)

        result = asyncio.run(parent())
        assert result == "req-async"

    def test_propagates_to_gather(self):
        async def child(suffix: str):
            return TraceContext.get_trace_id() + "-" + suffix

        async def parent():
            token = TraceContext.set_trace_id("req-gather")
            try:
                results = await asyncio.gather(
                    child("a"),
                    child("b"),
                    child("c"),
                )
                return results
            finally:
                TraceContext.reset(token)

        results = asyncio.run(parent())
        assert results == ["req-gather-a", "req-gather-b", "req-gather-c"]

    def test_isolated_after_reset(self):
        """reset 后子 Task 看到 None（不是上一轮的 trace_id）"""
        captured: list = []

        async def child():
            captured.append(TraceContext.get_trace_id())

        async def parent():
            token = TraceContext.set_trace_id("req-1st")
            try:
                await asyncio.create_task(child())
            finally:
                TraceContext.reset(token)
            await asyncio.create_task(child())

        asyncio.run(parent())
        assert captured == ["req-1st", None]
