"""OAuth 客户端注册端点 — RFC 7591 Dynamic Client Registration"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.interface.api.deps.auth import get_current_user_id
from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models.oauth import OAuthClient
from app.interface.api.schemas.oidc import (
    ClientRegisterRequest,
    ClientUpdateRequest,
    ClientResponse,
    ClientSecretResponse,
)

router = APIRouter(prefix="/register", tags=["OAuth Client Registration"])


def _to_client_response(client: OAuthClient) -> ClientResponse:
    return ClientResponse(
        client_id=client.client_id,
        client_name=client.name,
        description=client.description,
        redirect_uris=client.callback_urls,
        grant_types=[g.value for g in client.grant_types],
        scopes=client.scopes,
        homepage_url=client.homepage_url,
        logo_url=client.logo_url,
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


def _generate_client_id() -> str:
    """生成客户端 ID"""
    return f"oidc_{secrets.token_hex(16)}"


def _generate_client_secret() -> str:
    """生成客户端密钥"""
    return secrets.token_urlsafe(48)


@router.post("", response_model=ClientSecretResponse, status_code=201)
async def register_client(
    body: ClientRegisterRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """注册新的 OAuth 客户端（类似 GitHub OAuth Apps 注册）

    需要用户登录。
    """
    # 检查重名
    existing = await session.exec(
        select(OAuthClient).where(OAuthClient.name == body.client_name)
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="Client name already exists")

    from app.infrastructure.persistence.models.oauth import GrantTypeEnum, ClientAuthMethod

    client = OAuthClient(
        client_id=_generate_client_id(),
        client_secret=_generate_client_secret(),
        name=body.client_name,
        description=body.description,
        callback_urls=body.redirect_uris,
        owner_id=user_id,
        grant_types=[
            GrantTypeEnum(g) for g in body.grant_types
        ],
        scopes=body.scopes,
        token_endpoint_auth_method=ClientAuthMethod(
            body.token_endpoint_auth_method
        ),
        homepage_url=body.homepage_url,
        logo_url=body.logo_url,
    )
    session.add(client)
    await session.commit()
    await session.refresh(client)

    return ClientSecretResponse(
        client_id=client.client_id,
        client_secret=client.client_secret,
        client_name=client.name,
        description=client.description,
        redirect_uris=client.callback_urls,
        grant_types=[g.value for g in client.grant_types],
        scopes=client.scopes,
        homepage_url=client.homepage_url,
        logo_url=client.logo_url,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """列出当前用户拥有的所有 OAuth 客户端"""
    result = await session.exec(
        select(OAuthClient).where(OAuthClient.owner_id == user_id)
    )
    return [_to_client_response(c) for c in result.all()]


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """获取指定 OAuth 客户端详情"""
    client = await _get_user_client(session, client_id, user_id)
    return _to_client_response(client)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    body: ClientUpdateRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """更新 OAuth 客户端配置"""
    client = await _get_user_client(session, client_id, user_id)

    update_data = body.model_dump(exclude_unset=True)
    if "redirect_uris" in update_data:
        client.callback_urls = update_data["redirect_uris"]
    if "grant_types" in update_data:
        from app.infrastructure.persistence.models.oauth import GrantTypeEnum
        client.grant_types = [GrantTypeEnum(g) for g in update_data["grant_types"]]
    if "scopes" in update_data:
        client.scopes = update_data["scopes"]
    for field in ["client_name", "description", "homepage_url", "logo_url", "is_active"]:
        if field in update_data:
            if field == "client_name":
                client.name = update_data[field]
            else:
                setattr(client, field, update_data[field])

    client.updated_at = datetime.now(timezone.utc)
    session.add(client)
    await session.commit()
    await session.refresh(client)

    return _to_client_response(client)


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """删除 OAuth 客户端"""
    client = await _get_user_client(session, client_id, user_id)
    client.is_active = False
    session.add(client)
    await session.commit()
    return {"message": "Client deactivated"}


@router.post("/{client_id}/rotate-secret", response_model=ClientSecretResponse)
async def rotate_secret(
    client_id: str,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """轮换客户端密钥"""
    client = await _get_user_client(session, client_id, user_id)
    client.client_secret = _generate_client_secret()
    client.updated_at = datetime.now(timezone.utc)
    session.add(client)
    await session.commit()
    await session.refresh(client)

    return ClientSecretResponse(
        client_id=client.client_id,
        client_secret=client.client_secret,
        client_name=client.name,
        description=client.description,
        redirect_uris=client.callback_urls,
        grant_types=[g.value for g in client.grant_types],
        scopes=client.scopes,
        homepage_url=client.homepage_url,
        logo_url=client.logo_url,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


async def _get_user_client(
    session: AsyncSession, client_id: str, user_id: int,
) -> OAuthClient:
    """获取用户拥有的客户端，或 404"""
    result = await session.exec(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.owner_id == user_id,
        )
    )
    client = result.first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client