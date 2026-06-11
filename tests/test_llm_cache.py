# tests/test_llm_cache.py
"""测试 LLM 缓存"""
import sys
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.llm_cache import LLMCache, get_cache_stats, clear_cache


class TestLLMCache:
    """测试 LLM 缓存"""

    def setup_method(self):
        """测试前准备"""
        clear_cache()
        self.cache = LLMCache()

    def test_cache_key_generation(self):
        """测试缓存键生成"""
        key1 = self.cache._get_cache_key("test prompt", 0.1)
        key2 = self.cache._get_cache_key("test prompt", 0.1)
        key3 = self.cache._get_cache_key("different prompt", 0.1)

        # 相同输入应生成相同键
        assert key1 == key2
        # 不同输入应生成不同键
        assert key1 != key3

    def test_set_and_get(self):
        """测试保存和获取缓存"""
        prompt = "test prompt"
        response = "test response"

        # 保存缓存
        self.cache.set(prompt, response)

        # 获取缓存
        cached = self.cache.get(prompt)
        assert cached == response

    def test_cache_miss(self):
        """测试缓存未命中"""
        cached = self.cache.get("nonexistent prompt")
        assert cached is None

    def test_different_temperature(self):
        """测试不同温度参数"""
        prompt = "test prompt"
        response1 = "response for temp 0.1"
        response2 = "response for temp 0.9"

        self.cache.set(prompt, response1, temperature=0.1)
        self.cache.set(prompt, response2, temperature=0.9)

        cached1 = self.cache.get(prompt, temperature=0.1)
        cached2 = self.cache.get(prompt, temperature=0.9)

        assert cached1 == response1
        assert cached2 == response2

    def test_clear_cache(self):
        """测试清空缓存"""
        self.cache.set("test", "response")
        assert self.cache.get("test") == "response"

        clear_cache()
        assert self.cache.get("test") is None

    def test_cache_stats(self):
        """测试缓存统计"""
        self.cache.set("prompt1", "response1")
        self.cache.set("prompt2", "response2")

        stats = get_cache_stats()
        assert stats["memory_cache_size"] == 2
        assert stats["disk_cache_size"] >= 2


class TestLLMClientWithCache:
    """测试带缓存的 LLM 客户端"""

    @patch('src.core.llm_client.call_llm')
    def test_cache_hit(self, mock_call_llm):
        """测试缓存命中"""
        from src.core.llm_client import call_llm_with_prompt

        # 第一次调用：应调用 LLM
        mock_call_llm.return_value = MagicMock(content="cached response")
        result1 = call_llm_with_prompt("test prompt")

        # 第二次调用：应使用缓存，不调用 LLM
        mock_call_llm.reset_mock()
        result2 = call_llm_with_prompt("test prompt")

        assert result1 == result2
        mock_call_llm.assert_not_called()

    @patch('src.core.llm_client.call_llm')
    def test_cache_disabled(self, mock_call_llm):
        """测试禁用缓存"""
        from src.core.llm_client import call_llm_with_prompt

        mock_call_llm.return_value = MagicMock(content="response")

        # 使用缓存
        call_llm_with_prompt("test prompt", use_cache=True)
        # 禁用缓存
        call_llm_with_prompt("test prompt", use_cache=False)

        # 应调用两次
        assert mock_call_llm.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])