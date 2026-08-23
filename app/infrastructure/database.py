import asyncio
import logging
import os
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import elements
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.config.database import DatabaseSettings
from app.infrastructure.prometheus import (
    DB_POOL_SIZE,
    DB_ACTIVE_CONNECTIONS,
    DB_QUERY_DURATION,
    DB_QUERY_COUNTER,
    DB_IDLE_CONNECTIONS,
)

PROMETHEUS_LABEL = "postgres"
_logger = logging.getLogger("database")
metrics_executor = ThreadPoolExecutor(max_workers=min(4, os.cpu_count() // 2))


def process_batch(batch: list):
    """处理批量的指标记录（同步执行）"""
    try:
        for duration, operation in batch:
            DB_QUERY_DURATION.labels(db_type=PROMETHEUS_LABEL).observe(duration)
            DB_QUERY_COUNTER.labels(
                db_type="postgres",
                operation=operation,
            ).inc()
    except Exception as e:
        print(f"批量指标处理失败: {str(e)}")


class MetricBatcher:
    """线程安全的指标批处理器"""

    def __init__(self, max_batch_size: int = 100):
        self.batch = deque(maxlen=max_batch_size)
        self.lock = threading.Lock()
        self.max_batch_size = max_batch_size

    def add(self, duration: float, operation: str):
        """添加指标到批处理队列"""
        with self.lock:
            self.batch.append((duration, operation))
            if len(self.batch) >= self.max_batch_size:
                self._trigger_flush()

    def _trigger_flush(self):
        """触发批处理（内部使用）"""
        with self.lock:
            current_batch = list(self.batch)
            self.batch.clear()
        if current_batch:
            asyncio.get_event_loop().run_in_executor(
                metrics_executor,
                process_batch,
                current_batch,
            )

    def flush(self):
        """强制刷新剩余指标"""
        self._trigger_flush()


metric_batcher = MetricBatcher(max_batch_size=100)


def setup_async_db_metrics(engine: AsyncEngine, max_overflow: int = 5):
    """SQLAlchemy 2.x 标准监控方案（带线程池优化）"""
    loop = asyncio.get_event_loop()
    pool = engine.sync_engine.pool

    # StaticPool（SQLite）无 size/checkedout 方法，跳过连接池水位指标监听
    pool_size = getattr(pool, "size", lambda: 1)
    DB_POOL_SIZE.labels(db_type=PROMETHEUS_LABEL).set(pool_size() + max_overflow)

    if hasattr(pool, "checkedout") and hasattr(pool, "checkedin"):
        @event.listens_for(pool, "checkout")
        def _on_checkout(dbapi_conn, connection_record, connection_proxy):
            checked_out = pool.checkedout()
            idle = pool.checkedin()
            DB_ACTIVE_CONNECTIONS.labels(PROMETHEUS_LABEL).set(checked_out)
            DB_IDLE_CONNECTIONS.labels(PROMETHEUS_LABEL).set(idle)

        @event.listens_for(pool, "checkin")
        def _on_checkin(dbapi_conn, connection_record):
            checked_out = pool.checkedout()
            idle = pool.checkedin()
            DB_ACTIVE_CONNECTIONS.labels(PROMETHEUS_LABEL).set(checked_out)
            DB_IDLE_CONNECTIONS.labels(PROMETHEUS_LABEL).set(idle)

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_query(conn, cursor, stmt, params, context, executemany):
        context._query_start = loop.time()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_query(conn, cursor, stmt, params, context, executemany):
        duration = max(loop.time() - context._query_start, 0)
        if isinstance(stmt, elements.ClauseElement):
            operation = stmt.compile().string.split()[0].upper()
        else:
            operation = str(stmt).split()[0].upper()[:10]

        metric_batcher.add(duration, operation)


async def periodic_flush():
    while True:
        await asyncio.sleep(5)
        metric_batcher.flush()


def close_metrics():
    metric_batcher.flush()
    metrics_executor.shutdown(wait=True)


class DatabaseManager:
    """数据库运行时管理: 引擎创建、session、健康检查"""

    def __init__(self, settings: DatabaseSettings | None = None):
        self._settings = settings or DatabaseSettings()
        self._engine: AsyncEngine | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = self._create_engine()
            setup_async_db_metrics(self._engine, self._settings.DB_MAXSIZE - self._settings.DB_MINSIZE)
        return self._engine

    def _create_engine(self) -> AsyncEngine:
        """按引擎类型创建异步引擎

        - SQLite: StaticPool + check_same_thread 关闭（单连接，避免文件锁冲突）
        - PostgreSQL: server_settings 应用名 + 连接池调优
        - MySQL: utf8mb4 字符集 + 连接池调优
        """
        if self._settings.is_sqlite:
            return create_async_engine(
                self._settings.db_url,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )

        engine_kwargs = {
            "pool_size": self._settings.DB_MINSIZE,
            "max_overflow": self._settings.DB_MAXSIZE - self._settings.DB_MINSIZE,
            "pool_timeout": self._settings.DB_COMMAND_TIMEOUT,
            "pool_recycle": self._settings.DB_MAX_INACTIVE_CONNECTION_LIFETIME,
            "pool_use_lifo": True,
            "pool_pre_ping": True,
        }
        if self._settings.is_mysql:
            engine_kwargs["connect_args"] = {"charset": "utf8mb4"}
        else:
            engine_kwargs["connect_args"] = {
                "server_settings": {"application_name": self._settings.APP_NAME}
            }
        return create_async_engine(self._settings.db_url, **engine_kwargs)

    @property
    def async_session(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            future=True,
        )

    async def close_all(self):
        if self._engine:
            await self._engine.dispose()

    async def healthy(self):
        try:
            async with self.session() as connect:
                result = await connect.exec(select(text("1")))
                return result.one() == 1
        except Exception as e:
            _logger.error(f"Database healthy check failed: {e}")
            return False

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """异步 session 上下文管理器, 自带 commit/rollback/close"""
        async with self.async_session() as session:
            yield session


# 全局单例
_db_manager = DatabaseManager()


async def get_db_session():
    """
    FastAPI 依赖注入: 提供数据库 session
    """
    async with _db_manager.async_session() as session:
        yield session
