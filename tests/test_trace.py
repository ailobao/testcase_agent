"""测试请求追踪 ID"""
import sys
import os
import pytest
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.trace import (
    generate_trace_id, set_trace_id, get_trace_id,
    clear_trace_id, TraceAdapter
)


class TestTrace:
    """测试追踪 ID"""

    def test_generate_trace_id(self):
        """测试生成追踪 ID"""
        trace_id = generate_trace_id()
        assert trace_id is not None
        assert len(trace_id) > 20  # 包含时间戳和 UUID
        assert "_" in trace_id  # 格式：时间戳_UUID

    def test_generate_unique_ids(self):
        """测试生成的 ID 唯一性"""
        ids = set()
        for _ in range(100):
            ids.add(generate_trace_id())
        assert len(ids) == 100

    def test_set_and_get_trace_id(self):
        """测试设置和获取追踪 ID"""
        trace_id = set_trace_id("test-123")
        assert get_trace_id() == "test-123"

        clear_trace_id()
        assert get_trace_id() is None

    def test_auto_generate(self):
        """测试自动生成追踪 ID"""
        trace_id = set_trace_id()  # 不传参数，自动生成
        assert get_trace_id() == trace_id

    def test_trace_adapter(self):
        """测试日志适配器自动添加 trace_id"""
        logger = logging.getLogger("test_trace_adapter")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        from io import StringIO
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)

        # 设置追踪 ID
        set_trace_id("trace-001")

        # 使用适配器
        adapter = TraceAdapter(logger)
        adapter.info("测试消息")

        # 验证消息包含追踪 ID
        output = stream.getvalue()
        assert "[trace-001]" in output
        assert "测试消息" in output

        clear_trace_id()

    def test_context_isolation(self):
        """测试线程间上下文隔离"""
        from threading import Thread

        results = []

        def worker(name):
            set_trace_id(f"thread-{name}")
            results.append(get_trace_id())
            clear_trace_id()

        threads = [Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 每个线程应该有自己的 trace_id
        assert len(set(results)) == 5

    def test_base_agent_trace_methods(self):
        """测试 BaseAgent 的 trace 方法"""
        from src.agents.base_agent import BaseAgent

        # 用简单子类测试
        class TestAgent(BaseAgent):
            def generate(self, **kwargs):
                return None

        agent = TestAgent()
        assert agent._trace_id is None
        assert agent.get_trace_id() is None

        # 开始追踪
        trace_id = agent.start_trace()
        assert trace_id is not None
        assert agent._trace_id == trace_id
        assert get_trace_id() == trace_id

        # 结束追踪后仍可通过 agent 获取
        agent.end_trace()
        assert agent.get_trace_id() == trace_id
        # 但 ContextVar 已被清除
        assert get_trace_id() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
