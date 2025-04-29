import asyncio
from tortoise import Tortoise
from tortoise.exceptions import DBConnectionError

from app.utils.redis import get_redis


class HealthCheck:
    @staticmethod
    async def check_postgres():
        """检查 PostgreSQL 连接"""
        try:
            conn = Tortoise.get_connection("default")
            await conn.execute_query("SELECT 1")
            return True
        except DBConnectionError:
            return False

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
