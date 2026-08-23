from redis.asyncio import ConnectionPool, Redis

from app.infrastructure.config.redis import RedisSettings


class RedisManager:
    """Redis 运行时管理: 连接池创建、客户端获取"""

    def __init__(self, settings: RedisSettings | None = None):
        self._settings = settings or RedisSettings()
        self._pool: ConnectionPool | None = None

    @property
    def pool(self) -> ConnectionPool:
        if self._pool is None:
            self._pool = ConnectionPool(**self._settings.connection_pool_kw)
        return self._pool


# 全局单例
_redis_manager = RedisManager()


async def get_redis():
    """获取 Redis 客户端（异步生成器, 自动关闭连接）"""
    redis = Redis(connection_pool=_redis_manager.pool)
    try:
        yield redis
    finally:
        await redis.close()
