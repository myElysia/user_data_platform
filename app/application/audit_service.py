from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.persistence.models import (
    AuditLog,
    TransformLog
)

from app.infrastructure.persistence.base import ModelService
from app.infrastructure.persistence.repositories import SqlAuditRepository


class AuditLogService(ModelService[AuditLog]):
    ...


class TransformLogService(ModelService[TransformLog]):
    ...


class AuditService:
    """审计日志查询服务（第六阶段：结构化事件查询与过滤）"""

    def __init__(self, session: AsyncSession):
        self._repo = SqlAuditRepository(session)

    async def query(
        self,
        *,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        start_time=None,
        end_time=None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[AuditLog]]:
        """分页查询审计事件（按 action/user/时间段过滤）"""
        return await self._repo.query(
            action=action,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            skip=skip,
            limit=limit,
        )


async def record_audit(
    session: AsyncSession,
    user_id: int,
    action: str,
    ip_address: str = "",
    operation_type: str = "AUTH",
    target_resource_id: Optional[int] = None,
    request_metadata: Optional[dict] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
) -> None:
    """结构化审计事件落库（第六阶段完整审计体系的核心写入器）"""
    session.add(AuditLog(
        user_id=user_id,
        action=action,
        ip_address=ip_address,
        target_resource_id=target_resource_id,
        request_metadata=request_metadata or {},
        operation_type=operation_type,
        old_value=old_value,
        new_value=new_value,
    ))
    await session.commit()
