from redis.asyncio import Redis, ConnectionPool

from config.redis import Settings

settings = Settings()

redis_pool = ConnectionPool(**settings.connection_pool_kw)


async def get_redis():
    redis = Redis(connection_pool=redis_pool)
    try:
        yield redis
    finally:
        await redis.close()
