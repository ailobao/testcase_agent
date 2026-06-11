# scripts/cache_manager.py
"""LLM 缓存管理工具"""
import sys
import os
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.llm_cache import get_cache_stats, clear_cache


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="LLM 缓存管理工具")
    parser.add_argument("--stats", "-s", action="store_true", help="显示缓存统计")
    parser.add_argument("--clear", "-c", action="store_true", help="清空所有缓存")
    parser.add_argument("--info", "-i", action="store_true", help="显示缓存目录信息")

    args = parser.parse_args()

    if args.stats:
        stats = get_cache_stats()
        print("\n" + "=" * 50)
        print("LLM 缓存统计")
        print("=" * 50)
        print(f"内存缓存大小: {stats['memory_cache_size']} 条")
        print(f"磁盘缓存大小: {stats['disk_cache_size']} 条")
        print(f"缓存目录: {stats['cache_dir']}")
        print(f"缓存有效期: {stats['ttl_hours']} 小时")
        print(f"最大缓存数: {stats['max_cache_size']} 条")
        print("=" * 50)

    if args.info:
        stats = get_cache_stats()
        print("\n" + "=" * 50)
        print("缓存目录信息")
        print("=" * 50)
        print(f"目录路径: {stats['cache_dir']}")

        cache_dir = Path(stats['cache_dir'])
        if cache_dir.exists():
            files = list(cache_dir.glob("*.json"))
            if files:
                print(f"\n缓存文件列表 (共 {len(files)} 个):")
                for f in files[:10]:  # 只显示前10个
                    size = f.stat().st_size
                    print(f"  - {f.name} ({size} bytes)")
                if len(files) > 10:
                    print(f"  ... 还有 {len(files) - 10} 个文件")
            else:
                print("\n缓存目录为空")
        else:
            print("\n缓存目录不存在")
        print("=" * 50)

    if args.clear:
        confirm = input("确定要清空所有缓存吗？(y/N): ")
        if confirm.lower() == 'y':
            clear_cache()
            print("✅ 缓存已清空")
        else:
            print("❌ 已取消")

    if not any([args.stats, args.clear, args.info]):
        parser.print_help()


if __name__ == "__main__":
    main()