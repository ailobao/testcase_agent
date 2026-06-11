"""测试 LLM 缓存监控 - 命中率统计"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.llm_cache import (
    LLMCache, get_cache_stats, clear_cache,
    reset_cache_stats, log_cache_stats, get_cached_response,
    set_cached_response
)


class TestCacheMonitor:
    """缓存监控统计"""

    def setup_method(self):
        clear_cache()
        self.cache = LLMCache()

    def test_initial_stats_zero(self):
        """初始统计应为 0"""
        assert self.cache.hit_count == 0
        assert self.cache.miss_count == 0
        assert self.cache.save_count == 0
        assert self.cache.total_requests == 0
        assert self.cache.hit_rate == 0.0

    def test_hit_count_increments(self):
        """命中后 hit_count 递增"""
        self.cache.set("prompt", "response")
        result = self.cache.get("prompt")
        assert result == "response"
        assert self.cache.hit_count == 1
        assert self.cache.miss_count == 0

    def test_miss_count_increments(self):
        """未命中后 miss_count 递增"""
        result = self.cache.get("不存在的prompt")
        assert result is None
        assert self.cache.hit_count == 0
        assert self.cache.miss_count == 1

    def test_mixed_hit_miss(self):
        """混合场景统计正确"""
        self.cache.set("prompt1", "response1")

        self.cache.get("prompt1")       # hit
        self.cache.get("prompt2")       # miss
        self.cache.get("prompt1")       # hit
        self.cache.get("prompt3")       # miss

        assert self.cache.hit_count == 2
        assert self.cache.miss_count == 2
        assert self.cache.total_requests == 4
        assert self.cache.hit_rate == 0.5

    def test_save_count_increments(self):
        """保存后 save_count 递增"""
        self.cache.set("a", "1")
        assert self.cache.save_count == 1
        self.cache.set("b", "2")
        assert self.cache.save_count == 2

    def test_hit_rate_percent_format(self):
        """命中率百分比格式"""
        self.cache.set("p", "r")
        self.cache.get("p")              # hit
        self.cache.get("missing")        # miss

        stats = self.cache.get_stats()
        assert stats["hit_rate_percent"] == "50.0%"
        assert stats["hit_rate"] == 0.5

    def test_hit_rate_zero_when_no_requests(self):
        """无请求时命中率为 0.0"""
        assert self.cache.hit_rate == 0.0

    def test_hit_rate_one_hundred_percent(self):
        """全命中时命中率为 100%"""
        self.cache.set("p", "r")
        self.cache.get("p")
        self.cache.get("p")
        assert self.cache.hit_rate == 1.0
        assert self.cache.get_stats()["hit_rate_percent"] == "100.0%"

    def test_reset_stats(self):
        """重置统计"""
        self.cache.set("p", "r")
        self.cache.get("p")     # hit
        self.cache.get("x")     # miss
        assert self.cache.hit_count == 1
        assert self.cache.miss_count == 1

        reset_cache_stats()
        assert self.cache.hit_count == 0
        assert self.cache.miss_count == 0
        assert self.cache.save_count == 0
        # 缓存数据仍然保留（只重置计数）
        assert self.cache.get("p") == "r"

    def test_clear_resets_stats(self):
        """clear_cache 应同时重置统计"""
        self.cache.set("p", "r")
        self.cache.get("p")     # hit

        clear_cache()
        assert self.cache.hit_count == 0
        assert self.cache.miss_count == 0

    def test_get_stats_contains_monitoring_fields(self):
        """get_stats 包含监控字段"""
        self.cache.set("p", "r")
        self.cache.get("p")     # hit

        stats = self.cache.get_stats()
        assert "hit_count" in stats
        assert "miss_count" in stats
        assert "save_count" in stats
        assert "total_requests" in stats
        assert "hit_rate" in stats
        assert "hit_rate_percent" in stats
        assert stats["hit_count"] == 1

    def test_log_cache_stats_no_error(self):
        """log_cache_stats 不抛异常"""
        self.cache.set("p", "r")
        self.cache.get("p")     # hit
        self.cache.get("x")     # miss
        # 只是测试不抛异常
        log_cache_stats()

    def test_concurrent_get_set_updates_stats(self):
        """get_cached_response / set_cached_response 也更新统计"""
        clear_cache()

        # miss
        result = get_cached_response("prompt")
        assert result is None

        # set then hit
        set_cached_response("prompt", "response")
        result = get_cached_response("prompt")
        assert result == "response"

        stats = get_cache_stats()
        assert stats["hit_count"] == 1
        assert stats["miss_count"] == 1
        assert stats["save_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
