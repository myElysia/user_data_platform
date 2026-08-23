"""CacheBackend 抽象 — Redis 可用走 RedisBackend，不可用降级 MemoryBackend

启动时（首次调用 get_cache_backend）对 Redis 做一次 ping 探测决定后端；
后续调用直接复用已选后端（惰性单例，进程生命周期内不切换）。
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.infrastructure.log import AsyncLogger
from app.infrastructure.redis import get_redis

_logger = AsyncLogger.get_logger(**{"name": "cache"})


class CacheBackend(ABC):
    """缓存后端抽象接口（限流/验证码等场景使用的操作子集）"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """读取键值，不存在/已过期返回 None"""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """写入键值，ttl 秒"""

    @abstractmethod
    async def setex(self, key: str, ttl: int, value: Any) -> None:
        """写入键值并设置过期时间（秒）"""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除键"""

    # ---- 有序集合（滑动窗口限流） ----

    @abstractmethod
    async def zadd(self, key: str, mapping: Dict[str, float]) -> None:
        """向有序集合添加成员（member -> score）"""

    @abstractmethod
    async def zcard(self, key: str) -> int:
        """返回有序集合成员数（自动清理过期成员）"""

    @abstractmethod
    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """按分数区间删除成员，返回删除数量"""

    @abstractmethod
    async def ping(self) -> bool:
        """连通性探测"""


# ---------------------------------------------------------------------------
# Redis 后端
# ---------------------------------------------------------------------------

class RedisBackend(CacheBackend):
    """基于 Redis 的缓存后端（生产模式）"""

    async def get(self, key: str) -> Optional[Any]:
        async for redis in get_redis():
            return await redis.get(key)
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async for redis in get_redis():
            await redis.set(key, value, ex=ttl)
            return

    async def setex(self, key: str, ttl: int, value: Any) -> None:
        async for redis in get_redis():
            await redis.setex(key, ttl, value)
            return

    async def delete(self, key: str) -> None:
        async for redis in get_redis():
            await redis.delete(key)
            return

    async def zadd(self, key: str, mapping: Dict[str, float]) -> None:
        async for redis in get_redis():
            await redis.zadd(key, mapping)
            return

    async def zcard(self, key: str) -> int:
        async for redis in get_redis():
            return int(await redis.zcard(key))
        return 0

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        async for redis in get_redis():
            return int(await redis.zremrangebyscore(key, min_score, max_score))
        return 0

    async def ping(self) -> bool:
        try:
            async for redis in get_redis():
                return bool(await redis.ping())
        except Exception:
            return False
        return False


# ---------------------------------------------------------------------------
# 内存后端（Redis 不可用时的降级实现）
# ---------------------------------------------------------------------------

class MemoryBackend(CacheBackend):
    """进程内缓存后端 — dict + 时间戳过期清理（单进程降级模式）

    有序集合以 {member: score} dict 模拟；过期成员在 zcard/zremrangebyscore
    访问时惰性清理，无需显式 TTL。
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}
        self._zsets: Dict[str, Dict[str, float]] = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, key: str) -> bool:
        ttl = self._expires.get(key)
        if ttl is None:
            return False
        if time.time() > ttl:
            self._store.pop(key, None)
            self._expires.pop(key, None)
            return True
        return False

    def _purge_zset(self, key: str, min_score: float, max_score: float) -> int:
        """删除 min_score <= score <= max_score 的成员，返回删除数"""
        zset = self._zsets.get(key)
        if not zset:
            return 0
        stale = [m for m, s in zset.items() if min_score <= s <= max_score]
        for m in stale:
            del zset[m]
        if not zset:
            self._zsets.pop(key, None)
        return len(stale)

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if self._is_expired(key):
                return None
            return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            self._store[key] = value
            self._expires.pop(key, None)
            if ttl:
                self._expires[key] = time.time() + ttl

    async def setex(self, key: str, ttl: int, value: Any) -> None:
        await self.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)
            self._expires.pop(key, None)
            self._zsets.pop(key, None)

    async def zadd(self, key: str, mapping: Dict[str, float]) -> None:
        async with self._lock:
            zset = self._zsets.setdefault(key, {})
            zset.update(mapping)

    async def zcard(self, key: str) -> int:
        async with self._lock:
            return len(self._zsets.get(key, {}))

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        async with self._lock:
            return self._purge_zset(key, float(min_score), float(max_score))

    async def ping(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# 后端选择（惰性单例）
# ---------------------------------------------------------------------------

_backend: Optional[CacheBackend] = None
_backend_lock = asyncio.Lock()


async def get_cache_backend() -> CacheBackend:
    """获取缓存后端 — 首次调用时 ping Redis 决定，之后复用"""
    global _backend
    if _backend is not None:
        return _backend
    async with _backend_lock:
        if _backend is not None:
            return _backend
        redis_backend = RedisBackend()
        if await redis_backend.ping():
            _backend = redis_backend
            await _logger.info("CacheBackend: Redis 可用，使用 RedisBackend")
        else:
            _backend = MemoryBackend()
            await _logger.warning(
                "CacheBackend: Redis 不可用，降级使用 MemoryBackend（进程内缓存）",
            )
        return _backend
