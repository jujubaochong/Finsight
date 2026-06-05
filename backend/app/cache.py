"""
简易内存缓存（MVP 阶段替代 Redis）
生产环境可替换为 Redis 实现
"""
from __future__ import annotations
import time
from typing import Any, Optional
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class MemoryCache:
    """线程安全的 TTL 内存缓存"""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.time() < expires_at:
                return value
            else:
                del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        self._store[key] = (value, time.time() + ttl)

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def invalidate_prefix(self, prefix: str):
        """删除所有匹配前缀的缓存"""
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]


# 全局缓存实例
cache = MemoryCache()


def cached(prefix: str, ttl: int = 3600):
    """装饰器：缓存函数结果"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 构建缓存 key（跳过 db session 参数）
            key_parts = [str(a) for a in args[1:]]  # 跳过第一个参数（通常是 db）
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            raw_key = f"{prefix}:{':'.join(key_parts)}"
            cache_key = hashlib.md5(raw_key.encode()).hexdigest()

            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache HIT: {prefix}")
                return result

            logger.debug(f"Cache MISS: {prefix}")
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
