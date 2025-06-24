import asyncio
import os
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import cached_property
from typing import AsyncGenerator
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_core.core_schema import ValidationInfo
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
from sqlalchemy.sql import elements
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from . import EnvSettings
from .prometheus import (
    DB_POOL_SIZE,
    DB_ACTIVE_CONNECTIONS,
    DB_QUERY_DURATION,
    DB_QUERY_COUNTER,
    DB_IDLE_CONNECTIONS
)

PROMETHEUS_LABEL = "postgres"
metrics_executor = ThreadPoolExecutor(max_workers=min(4, os.cpu_count() // 2))


def process_batch(batch: list):
    """处理批量的指标记录（同步执行）"""
    try:
        for duration, operation in batch:
            # 记录查询耗时
            DB_QUERY_DURATION.labels(db_type=PROMETHEUS_LABEL).observe(duration)
            # 记录查询次数
            DB_QUERY_COUNTER.labels(
                db_type='postgres',
                operation=operation
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
                current_batch
            )

    def flush(self):
        """强制刷新剩余指标"""
        self._trigger_flush()


# 初始化批处理器（每批最多100条）
metric_batcher = MetricBatcher(max_batch_size=100)


def setup_async_db_metrics(engine: AsyncEngine, max_overflow: int = 5):
    """SQLAlchemy 2.x 标准监控方案（带线程池优化）"""
    loop = asyncio.get_event_loop()
    pool = engine.sync_engine.pool

    # 初始化连接池容量指标
    DB_POOL_SIZE.labels(db_type=PROMETHEUS_LABEL).set(pool.size() + max_overflow)

    @event.listens_for(pool, "checkout")
    def _on_checkout(dbapi_conn, connection_record, connection_proxy):
        # 直接通过连接池属性获取状态
        checked_out = pool.checkedout()
        idle = pool.checkedin()  # 如果存在 checkedin 属性
        # 或者通过计算：idle = pool.size() - checked_out
        DB_ACTIVE_CONNECTIONS.labels(PROMETHEUS_LABEL).set(checked_out)
        DB_IDLE_CONNECTIONS.labels(PROMETHEUS_LABEL).set(idle)

    @event.listens_for(pool, "checkin")
    def _on_checkin(dbapi_conn, connection_record):
        # 直接通过连接池属性获取状态
        checked_out = pool.checkedout()
        idle = pool.checkedin()
        # 或者通过计算：idle = pool.size() - checked_out
        DB_ACTIVE_CONNECTIONS.labels(PROMETHEUS_LABEL).set(checked_out)
        DB_IDLE_CONNECTIONS.labels(PROMETHEUS_LABEL).set(idle)

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_query(conn, cursor, stmt, params, context, executemany):
        context._query_start = loop.time()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_query(conn, cursor, stmt, params, context, executemany):
        # 计算耗时和操作类型
        duration = max(loop.time() - context._query_start, 0)
        if isinstance(stmt, elements.ClauseElement):
            operation = stmt.compile().string.split()[0].upper()
        else:
            operation = str(stmt).split()[0].upper()[:10]

        # 添加到批处理器（非阻塞）
        metric_batcher.add(duration, operation)


# 定时刷新批处理（每5秒）
async def periodic_flush():
    while True:
        await asyncio.sleep(5)
        metric_batcher.flush()


def close_metrics():
    metric_batcher.flush()
    metrics_executor.shutdown(wait=True)


class Settings(EnvSettings):
    APP_NAME: str = ""
    DB_ENGINE: str = 'postgresql+asyncpg'  # 修改为 SQLAlchemy 兼容的引擎格式
    DB_USER: str = ''
    DB_PASSWORD: str = ''
    DB_HOST: str = ''
    DB_PORT: int = 5432
    DB_DATABASE: str = ''
    DB_MINSIZE: int = 3
    DB_MAXSIZE: int = 20
    DB_COMMAND_TIMEOUT: int = 30
    DB_MAX_INACTIVE_CONNECTION_LIFETIME: int = 300  # 单位：秒

    @cached_property
    def prefix(self):
        return "DB_"

    @field_validator("DB_MAXSIZE")
    def validate_pool_size(cls, v, info: ValidationInfo):
        if v <= info.data["DB_MINSIZE"]:
            raise ValueError("DB_MAXSIZE must be greater than DB_MINSIZE")
        return v

    @property
    def _password(self):
        return quote_plus(self.DB_PASSWORD)

    @property
    def _db_url(self) -> str:
        """构建数据库 URL"""
        return (
            f"{self.DB_ENGINE}://{self.DB_USER}:{self._password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"
        )

    @property
    def async_engine(self):
        """创建异步引擎（带连接池配置）"""
        max_overflow = self.DB_MAXSIZE - self.DB_MINSIZE
        async_engine = create_async_engine(
            self._db_url,
            pool_size=self.DB_MINSIZE,
            max_overflow=max_overflow,
            pool_timeout=self.DB_COMMAND_TIMEOUT,
            pool_recycle=self.DB_MAX_INACTIVE_CONNECTION_LIFETIME,
            pool_use_lifo=True,  # 提高连接池效率
            pool_pre_ping=True,  # 自动检测失效连接
            connect_args={"server_settings": {"application_name": self.APP_NAME}}
        )
        setup_async_db_metrics(async_engine, max_overflow)
        return async_engine

    @property
    def async_session(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(bind=self.async_engine, class_=AsyncSession, expire_on_commit=False, future=True)

    async def depends(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Fastapi 依赖注入实现方法
        :return:
        """
        async with self.async_session() as session:
            yield session

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        async session 自带了 session.rollback 和 session.close, 所以此处不在实现
        :return:
        """
        async with self.async_session() as session:
            yield session

    async def close_all(self):
        await self.async_engine.dispose()

    async def healthy(self):
        try:
            async with self.session() as connect:
                result = await connect.exec(select(text("1")))
                return result.one() == 1
        except Exception as e:
            print(e)
            return False
