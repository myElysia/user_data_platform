"""审计日志 SQL 仓储 — 实现 domain AuditRepository 接口并扩展查询能力"""

from datetime import datetime
from typing import Optional

from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.security.repositories import AuditRepository
from app.infrastructure.persistence.models import AuditLog


class SqlAuditRepository(AuditRepository):
    """AuditLog 表读写实现（写侧供 record_audit 复用，查询侧供 AuditService）"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, **event) -> None:
        """写入结构化审计事件（字段：user_id/action/ip_address/...）"""
        self.session.add(AuditLog(**event))
        await self.session.commit()

    async def query(
        self,
        *,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[AuditLog]]:
        """分页查询审计日志，支持按 action/user/时间段过滤"""
        query = select(AuditLog)
        if action:
            query = query.where(AuditLog.action == action)
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        if start_time is not None:
            query = query.where(AuditLog.created_at >= start_time)
        if end_time is not None:
            query = query.where(AuditLog.created_at <= end_time)

        count_result = await self.session.exec(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.one()

        query = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.exec(query)
        return total, result.all()
