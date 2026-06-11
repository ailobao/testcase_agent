# src/utils/llm_cache.py
"""LLM 响应缓存 - 支持内存和磁盘缓存，含命中率监控"""
import os
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
CACHE_DIR = PROJECT_ROOT / ".llm_cache"
CACHE_TTL_HOURS = 24  # 缓存有效期 24 小时
MAX_CACHE_SIZE = 1000  # 最大缓存条目数

logger = logging.getLogger("main")


class LLMCache:
    """LLM 响应缓存管理器 — 含命中/未命中统计"""

    _instance = None
    _memory_cache: Dict[str, Dict[str, Any]] = {}

    # 监控统计
    _hit_count: int = 0
    _miss_count: int = 0
    _save_count: int = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_cache_dir()
        return cls._instance

    def _init_cache_dir(self):
        """初始化缓存目录"""
        CACHE_DIR.mkdir(exist_ok=True)
        # 清理过期缓存
        self._clean_expired_cache()

    def _get_cache_key(self, prompt: str, temperature: float = 0.1) -> str:
        """生成缓存键"""
        content = f"{prompt}|{temperature}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return CACHE_DIR / f"{cache_key}.json"

    def _is_cache_valid(self, cache_file: Path) -> bool:
        """检查缓存是否有效"""
        if not cache_file.exists():
            return False

        # 检查文件修改时间
        mod_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        age = datetime.now() - mod_time
        return age < timedelta(hours=CACHE_TTL_HOURS)

    def _clean_expired_cache(self):
        """清理过期缓存"""
        if not CACHE_DIR.exists():
            return

        for cache_file in CACHE_DIR.glob("*.json"):
            if not self._is_cache_valid(cache_file):
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.warning("清理过期缓存文件失败 %s: %s", cache_file.name, e)

    # ====================== 监控统计 ======================

    @property
    def hit_count(self) -> int:
        """获取缓存命中次数"""
        return self._hit_count

    @property
    def miss_count(self) -> int:
        """获取缓存未命中次数"""
        return self._miss_count

    @property
    def save_count(self) -> int:
        """获取缓存保存次数"""
        return self._save_count

    @property
    def total_requests(self) -> int:
        """获取总请求次数"""
        return self._hit_count + self._miss_count

    @property
    def hit_rate(self) -> float:
        """获取缓存命中率 (0.0 ~ 1.0)"""
        total = self.total_requests
        if total == 0:
            return 0.0
        return round(self._hit_count / total, 4)

    def reset_stats(self):
        """重置监控统计"""
        self._hit_count = 0
        self._miss_count = 0
        self._save_count = 0

    # ====================== 核心缓存操作 ======================

    def get(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        """获取缓存响应（自动统计命中/未命中）"""
        cache_key = self._get_cache_key(prompt, temperature)

        # 1. 检查内存缓存
        if cache_key in self._memory_cache:
            cache_entry = self._memory_cache[cache_key]
            if self._is_cache_valid(Path(cache_entry["file_path"])):
                self._hit_count += 1
                return cache_entry["response"]
            else:
                # 内存缓存过期，删除
                del self._memory_cache[cache_key]

        # 2. 检查磁盘缓存
        cache_file = self._get_cache_file_path(cache_key)
        if self._is_cache_valid(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    response = data.get("response")

                    # 加载到内存缓存
                    self._memory_cache[cache_key] = {
                        "response": response,
                        "file_path": str(cache_file),
                        "timestamp": datetime.now().isoformat()
                    }

                    self._hit_count += 1
                    return response
            except Exception as e:
                logger.warning("读取磁盘缓存失败: %s", e)
                self._miss_count += 1
                return None

        # 3. 未命中
        self._miss_count += 1
        return None

    def set(self, prompt: str, response: str, temperature: float = 0.1):
        """保存缓存响应"""
        cache_key = self._get_cache_key(prompt, temperature)
        cache_file = self._get_cache_file_path(cache_key)

        # 保存到磁盘
        try:
            data = {
                "cache_key": cache_key,
                "prompt_hash": cache_key,
                "response": response,
                "temperature": temperature,
                "created_at": datetime.now().isoformat(),
                "prompt_length": len(prompt)
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("保存缓存失败: %s", e)
            return

        # 保存到内存
        self._memory_cache[cache_key] = {
            "response": response,
            "file_path": str(cache_file),
            "timestamp": datetime.now().isoformat()
        }

        self._save_count += 1

        # 限制内存缓存大小
        if len(self._memory_cache) > MAX_CACHE_SIZE:
            # 删除最早的条目
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]

    def clear(self):
        """清空所有缓存"""
        self._memory_cache.clear()
        if CACHE_DIR.exists():
            for cache_file in CACHE_DIR.glob("*.json"):
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.warning("清除缓存文件失败 %s: %s", cache_file.name, e)
        self.reset_stats()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息（含命中率）"""
        disk_count = len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0

        return {
            "memory_cache_size": len(self._memory_cache),
            "disk_cache_size": disk_count,
            "cache_dir": str(CACHE_DIR),
            "ttl_hours": CACHE_TTL_HOURS,
            "max_cache_size": MAX_CACHE_SIZE,
            # 命中率统计
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "save_count": self._save_count,
            "total_requests": self.total_requests,
            "hit_rate": self.hit_rate,
            "hit_rate_percent": f"{self.hit_rate * 100:.1f}%",
        }


# 全局缓存实例
_llm_cache = LLMCache()


def get_cached_response(prompt: str, temperature: float = 0.1) -> Optional[str]:
    """获取缓存的响应"""
    return _llm_cache.get(prompt, temperature)


def set_cached_response(prompt: str, response: str, temperature: float = 0.1):
    """保存响应到缓存"""
    _llm_cache.set(prompt, response, temperature)


def clear_cache():
    """清空缓存"""
    _llm_cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计"""
    return _llm_cache.get_stats()


def reset_cache_stats():
    """重置缓存统计"""
    _llm_cache.reset_stats()


def log_cache_stats():
    """输出缓存统计到日志"""
    stats = _llm_cache.get_stats()
    logger.info(
        f"缓存统计: "
        f"命中={stats['hit_count']}, "
        f"未命中={stats['miss_count']}, "
        f"保存={stats['save_count']}, "
        f"命中率={stats['hit_rate_percent']}, "
        f"内存={stats['memory_cache_size']}, "
        f"磁盘={stats['disk_cache_size']}"
    )