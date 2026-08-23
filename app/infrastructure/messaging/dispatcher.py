"""ARQ 任务分发器 — Redis 可用走 ARQ 队列，不可用降级为进程内执行

使用方式:
    from app.infrastructure.messaging.dispatcher import dispatcher
    await dispatcher.enqueue("send_verification_email", email, code, purpose)
"""

import asyncio
from typing import Any, Optional

import arq

from app.infrastructure.log import AsyncLogger
from app.infrastructure.messaging.tasks import TASKS
from app.infrastructure.messaging.worker import build_worker_settings

_logger = AsyncLogger.get_logger(**{"name": "dispatcher"})


class TaskDispatcher:
    """任务分发器 — 惰性探测 Redis 后选择队列或内联模式"""

    def __init__(self):
        self._pool = None
        self._redis_ok: Optional[bool] = None
        self._probe_lock = asyncio.Lock()

    async def _ensure_pool(self) -> bool:
        """首次调用时探测 Redis；成功则建立 ARQ 连接池"""
        if self._redis_ok is not None:
            return self._redis_ok
        async with self._probe_lock:
            if self._redis_ok is not None:
                return self._redis_ok
            try:
                self._pool = await arq.create_pool(
                    build_worker_settings()["redis_settings"],
                )
                self._redis_ok = True
                await _logger.info("ARQ dispatcher: Redis 可用，任务将入队执行")
            except Exception as e:
                self._redis_ok = False
                await _logger.warning(
                    f"ARQ dispatcher: Redis 不可用（{e}），任务将降级为进程内执行",
                )
            return self._redis_ok

    async def enqueue(self, task_name: str, *args, **kwargs) -> str:
        """分发任务，返回执行模式（"queued" / "inline"）"""
        if task_name not in TASKS:
            raise ValueError(f"Unknown task: {task_name}")

        if await self._ensure_pool():
            await self._pool.enqueue_job(task_name, *args, **kwargs)
            return "queued"

        # 降级：进程内异步执行（不阻塞调用方，结果不等待）
        fn = TASKS[task_name]
        asyncio.create_task(fn(None, *args, **kwargs))
        return "inline"

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
            self._redis_ok = None


# 全局单例
dispatcher = TaskDispatcher()
