"""Webhook 管理端点"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.interface.api.deps.auth import get_current_user_id
from app.infrastructure.database import get_db_session
from app.application.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("")
async def create_webhook(
    url: str,
    events: list[str],
    client_id: int,
    description: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """创建 Webhook 订阅"""
    service = WebhookService(session)
    config = await service.create_config(
        client_id=client_id,
        url=url,
        events=events,
        description=description,
    )
    return {
        "id": config.id,
        "url": config.url,
        "secret": config.secret,
        "events": config.events,
        "is_active": config.is_active,
    }


@router.get("")
async def list_webhooks(
    client_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """列出客户端的 Webhook 配置"""
    service = WebhookService(session)
    configs = await service.get_client_configs(client_id)
    return [
        {
            "id": c.id,
            "url": c.url,
            "events": c.events,
            "is_active": c.is_active,
            "description": c.description,
            "created_at": c.created_at.isoformat(),
        }
        for c in configs
    ]


@router.get("/{config_id}/deliveries")
async def get_deliveries(
    config_id: int,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
):
    """获取 Webhook 投递历史"""
    service = WebhookService(session)
    deliveries = await service.get_deliveries(config_id, limit)
    return [
        {
            "id": d.id,
            "event_type": d.event_type,
            "status": d.status.value,
            "response_code": d.response_code,
            "attempts": d.attempts,
            "last_attempt_at": d.last_attempt_at.isoformat() if d.last_attempt_at else None,
            "created_at": d.created_at.isoformat(),
        }
        for d in deliveries
    ]
