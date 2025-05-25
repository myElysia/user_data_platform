from redis.asyncio import ConnectionPool, Redis

from app.local.redis import Settings

settings = Settings()

redis_pool = ConnectionPool(**settings.items)


async def get_redis():
    redis = Redis(connection_pool=redis_pool)
    try:
        yield redis
    finally:
        await redis.close()
