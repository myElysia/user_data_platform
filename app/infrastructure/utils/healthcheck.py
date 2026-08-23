"""启动健康检查 — DB 按配置引擎检查；Redis 不可用仅告警不阻断（优雅降级）"""

import asyncio

from app.infrastructure.database import DatabaseManager
from app.infrastructure.redis import get_redis
from app.infrastructure.log import AsyncLogger

database = DatabaseManager()
_logger = AsyncLogger.get_logger(**{"name": "healthcheck"})


class HealthCheck:
    @staticmethod
    async def check_db():
        """检查数据库连接（按 DB_ENGINE 配置，支持 SQLite/PG/MySQL）"""
        return await database.healthy()

    @staticmethod
    async def check_redis():
        """检查 Redis 连接 — 失败仅记录日志并返回 False，不抛异常"""
        try:
            async for redis in get_redis():
                return await redis.ping()
            return None
        except Exception as e:
            await _logger.warning(f"Redis check failed (will degrade): {e}")
            return False

    @classmethod
    async def run_all(cls):
        """执行所有检查

        - 数据库不可用：直接阻断启动（RuntimeError）
        - Redis 不可用：仅告警，服务以降级模式运行（MemoryBackend/inline 任务）
        """
        db_ok, redis_ok = await asyncio.gather(
            cls.check_db(),
            cls.check_redis()
        )
        if not db_ok:
            raise RuntimeError(f"服务不可用: 数据库检查失败 (DB_ENGINE={database._settings.DB_ENGINE})")
        if not redis_ok:
            await _logger.warning(
                "Redis 不可用，将以降级模式启动："
                "缓存使用 MemoryBackend、ARQ 任务内联执行、OIDC 授权码已入 DB",
            )
