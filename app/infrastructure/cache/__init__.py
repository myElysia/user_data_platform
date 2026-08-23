"""基础设施层缓存 — CacheBackend 抽象与双后端实现（Redis/Memory 优雅降级）"""

from app.infrastructure.cache.backend import (
    CacheBackend,
    RedisBackend,
    MemoryBackend,
    get_cache_backend,
)

__all__ = ["CacheBackend", "RedisBackend", "MemoryBackend", "get_cache_backend"]
