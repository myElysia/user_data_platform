"""管理员端点 — 第三方平台配置 CRUD（client_secret 加密存储）"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models.auth import (
    GrantType,
    OauthProvider,
    ProvideTypeEnum,
)
from app.interface.api.schemas.social import (
    ProviderCreateRequest,
    ProviderResponse,
    ProviderUpdateRequest,
)

router = APIRouter(prefix="/admin/providers", tags=["Admin - Social Providers"])

MASK = "********"


async def _admin_audit(session, action: str, new_value: str, target_resource_id: int = 0) -> None:
    """管理员操作审计（user_id=0 表示系统管理员操作）"""
    from app.application.audit_service import record_audit

    await record_audit(
        session, 0, action, ip_address="admin",
        operation_type="ADMIN", target_resource_id=target_resource_id,
        new_value=new_value,
    )


def _to_response(provider: OauthProvider) -> ProviderResponse:
    return ProviderResponse(
        id=provider.id,
        name=provider.name or "",
        icon=provider.icon,
        provider_type=provider.provider_type.value,
        grant_type=provider.grant_type.value,
        client_id=provider.client_id or "",
        client_secret_masked=MASK if provider.client_secret else "",
        authorization_url=provider.authorization_url or "",
        token_url=provider.token_url,
        userinfo_url=provider.userinfo_url,
        scope=provider.scope or "",
        additional_auth_params=provider.additional_auth_params or {},
        is_active=bool(provider.is_active),
        config_status=provider.config_status,
        login_count=provider.login_count,
        last_success_at=provider.last_success_at,
        created_at=provider.created_at,
    )


@router.get("")
async def list_providers(
    session: AsyncSession = Depends(get_db_session),
    skip: int = 0,
    limit: int = 50,
):
    """列出第三方平台配置（管理员）"""
    query = (
        select(OauthProvider)
        .where(OauthProvider.deleted_at == None)  # noqa: E711
        .offset(skip)
        .limit(limit)
    )
    result = await session.exec(query)
    providers = result.all()
    return {
        "total": len(providers),
        "providers": [_to_response(p).model_dump() for p in providers],
    }


@router.post("", response_model=ProviderResponse, status_code=201)
async def create_provider(
    body: ProviderCreateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """创建第三方平台配置（client_secret 加密落库）"""
    existing = await session.exec(
        select(OauthProvider).where(OauthProvider.name == body.name)
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="Provider name already exists")

    provider = OauthProvider(
        name=body.name,
        client_id=body.client_id,
        client_secret=body.client_secret,
        authorization_url=body.authorization_url,
        token_url=body.token_url,
        userinfo_url=body.userinfo_url,
        scope=body.scope,
        provider_type=ProvideTypeEnum(body.provider_type),
        grant_type=GrantType(body.grant_type),
        additional_auth_params=body.additional_auth_params,
        is_active=body.is_active,
        config_status=True,
    )
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    await _admin_audit(session, "admin_provider_create", provider.name,
                       target_resource_id=provider.id)
    return _to_response(provider)


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """获取平台配置详情（client_secret 脱敏）"""
    provider = await session.get(OauthProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _to_response(provider)


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    body: ProviderUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """更新平台配置（仅提供的字段生效）"""
    provider = await session.get(OauthProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(provider, field, value)
    provider.updated_at = datetime.now(timezone.utc)
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    await _admin_audit(session, "admin_provider_update", provider.name,
                       target_resource_id=provider.id)
    return _to_response(provider)


@router.put("/{provider_id}/toggle")
async def toggle_provider(
    provider_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """启用/禁用平台配置"""
    provider = await session.get(OauthProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.is_active = not provider.is_active
    session.add(provider)
    await session.commit()
    await _admin_audit(session, "admin_provider_toggle", provider.name,
                       target_resource_id=provider.id)
    return {
        "message": f"Provider {'activated' if provider.is_active else 'deactivated'}",
        "is_active": provider.is_active,
    }


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """软删除平台配置"""
    provider = await session.get(OauthProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.deleted_at = datetime.now(timezone.utc)
    provider.is_active = False
    session.add(provider)
    await session.commit()
    await _admin_audit(session, "admin_provider_delete", provider.name,
                       target_resource_id=provider.id)
    return {"message": "Provider deleted"}
