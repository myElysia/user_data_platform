"""管理员端点 — 审计日志查询（分页 + 按 action/user/时间段过滤）"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.audit_service import AuditService
from app.infrastructure.database import get_db_session

router = APIRouter(prefix="/admin/audit", tags=["Admin - Audit"])


@router.get("")
async def list_audit_logs(
    session: AsyncSession = Depends(get_db_session),
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
):
    """查询审计日志（管理员）

    - action: 按事件动作过滤（login_success/mfa_enabled/social_bound...）
    - user_id: 按用户过滤
    - start_time/end_time: 时间段过滤（ISO 8601）
    """
    service = AuditService(session)
    total, logs = await service.query(
        action=action,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        skip=skip,
        limit=limit,
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "logs": [
            {
                "id": log.id,
                "created_at": log.created_at,
                "user_id": log.user_id,
                "action": log.action,
                "ip_address": log.ip_address,
                "operation_type": log.operation_type,
                "target_resource_id": log.target_resource_id,
                "request_metadata": log.request_metadata,
                "old_value": log.old_value,
                "new_value": log.new_value,
            }
            for log in logs
        ],
    }
