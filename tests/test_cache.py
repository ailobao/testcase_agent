# 快速测试脚本 test_cache.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.llm_cache import get_cache_stats, clear_cache
from src.core.llm_client import call_llm_with_prompt

print("=" * 50)
print("LLM 缓存测试")
print("=" * 50)

# 清空缓存
clear_cache()
print("✅ 缓存已清空")

# 第一次调用（应调用 API）
print("\n1. 第一次调用（应该调用 LLM API）...")
response1 = call_llm_with_prompt("请说'你好'")
print(f"   响应: {response1[:100]}...")

# 第二次调用相同 prompt（应使用缓存）
print("\n2. 第二次调用相同 prompt（应该使用缓存）...")
response2 = call_llm_with_prompt("请说'你好'")
print(f"   响应: {response2[:100]}...")

# 检查缓存统计
stats = get_cache_stats()
print(f"\n缓存统计:")
print(f"  - 磁盘缓存: {stats['disk_cache_size']} 条")
print(f"  - 内存缓存: {stats['memory_cache_size']} 条")

print("\n" + "=" * 50)