"""管理员端点 — OAuth 客户端管理（类似 GitHub Admin 面板）"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models.oauth import OAuthClient
from app.interface.api.schemas.oidc import ClientResponse

router = APIRouter(prefix="/admin/clients", tags=["Admin - OAuth Clients"])


async def _admin_audit(session, action: str, target: str, **values) -> None:
    """管理员操作审计（user_id=0 表示系统管理员操作）"""
    from app.application.audit_service import record_audit

    await record_audit(
        session, 0, action, ip_address="admin",
        operation_type="ADMIN", target_resource_id=0,
        new_value=values.pop("new_value", f"client:{target}"), **values,
    )


def _to_response(client: OAuthClient) -> dict:
    return {
        "client_id": client.client_id,
        "client_name": client.name,
        "description": client.description,
        "redirect_uris": client.callback_urls,
        "grant_types": [g.value for g in client.grant_types],
        "scopes": client.scopes,
        "homepage_url": client.homepage_url,
        "logo_url": client.logo_url,
        "owner_id": client.owner_id,
        "is_active": client.is_active,
        "is_verified": client.is_verified,
        "created_at": client.created_at.isoformat(),
        "updated_at": client.updated_at.isoformat(),
    }


@router.get("")
async def list_all_clients(
    session: AsyncSession = Depends(get_db_session),
    skip: int = 0,
    limit: int = 50,
    is_active: bool = None,
):
    """列出所有 OAuth 客户端（管理员视角）"""
    query = select(OAuthClient)
    if is_active is not None:
        query = query.where(OAuthClient.is_active == is_active)
    query = query.offset(skip).limit(limit)
    result = await session.exec(query)
    clients = result.all()
    return {
        "total": len(clients),
        "clients": [_to_response(c) for c in clients],
    }


@router.get("/{client_id}")
async def get_client_detail(
    client_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """获取客户端详情（含敏感信息）"""
    result = await session.exec(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _to_response(client)


@router.put("/{client_id}/verify")
async def verify_client(
    client_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """验证客户端（管理员操作）"""
    result = await session.exec(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.is_verified = True
    session.add(client)
    await session.commit()
    await _admin_audit(session, "admin_client_verify", client_id)
    return {"message": "Client verified"}


@router.put("/{client_id}/toggle")
async def toggle_client(
    client_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """启用/禁用客户端"""
    result = await session.exec(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    old = client.is_active
    client.is_active = not client.is_active
    session.add(client)
    await session.commit()
    await _admin_audit(session, "admin_client_toggle", client_id,
                       old_value=str(old), new_value=str(client.is_active))
    return {
        "message": f"Client {'activated' if client.is_active else 'deactivated'}",
        "is_active": client.is_active,
    }