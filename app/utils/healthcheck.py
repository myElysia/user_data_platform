import asyncio
import logging

from app.utils.redis import get_redis
from app.local.database import Settings as Database

database = Database()
logger = logging.getLogger('healthcheck')


class HealthCheck:
    @staticmethod
    async def check_postgres():
        """检查 PostgreSQL 连接"""
        return await database.healthy()

    @staticmethod
    async def check_redis():
        """检查 Redis 连接"""
        try:
            async for redis in get_redis():
                return await redis.ping()
            return None
        except Exception as e:
            print(e)
            return False

    @classmethod
    async def run_all(cls):
        """执行所有检查"""
        pg_ok, redis_ok = await asyncio.gather(
            cls.check_postgres(),
            cls.check_redis()
        )
        if not all([pg_ok, redis_ok]):
            raise RuntimeError(
                f"服务不可用: PostgreSQL={pg_ok}, Redis={redis_ok}"
            )
