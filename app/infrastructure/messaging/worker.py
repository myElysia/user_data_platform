"""ARQ Worker 配置 — 生产模式独立 worker 进程（python main.py worker）"""

from arq.connections import RedisSettings as ArqRedisSettings

from app.infrastructure.config.redis import RedisSettings
from app.infrastructure.messaging.tasks import TASKS


def build_worker_settings() -> dict:
    """构建 arq.Worker 初始化参数（函数注册表 + Redis 连接配置）"""
    cfg = RedisSettings()
    return {
        "functions": TASKS,
        "redis_settings": ArqRedisSettings(
            host=cfg.REDIS_HOST,
            port=cfg.REDIS_PORT,
            password=cfg.REDIS_PASSWORD or None,
            database=cfg.REDIS_DB,
        ),
        "max_jobs": 10,
        "job_timeout": 60,
        "keep_result": 3600,
    }
