"""用户同意管理端点 — 查看/撤销 OAuth 授权"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.interface.api.deps.auth import get_current_user_id
from app.infrastructure.database import get_db_session
from app.application.oauth_services import ConsentService

router = APIRouter(prefix="/v1/consent", tags=["Consent Management"])


@router.get("")
async def list_consents(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """列出当前用户的所有 OAuth 授权记录"""
    service = ConsentService(session)
    from app.infrastructure.persistence.models.oauth import UserConsent
    from sqlmodel import select

    result = await session.exec(
        select(UserConsent).where(
            UserConsent.user_id == user_id,
        )
    )
    consents = result.all()

    return [
        {
            "id": c.id,
            "client_id": c.client_id,
            "scopes": c.scopes,
            "granted_at": c.granted_at.isoformat(),
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "is_expired": c.is_expired,
        }
        for c in consents
    ]


@router.delete("/{consent_id}")
async def revoke_consent(
    consent_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """撤销指定 OAuth 授权"""
    from app.infrastructure.persistence.models.oauth import UserConsent

    consent = await session.get(UserConsent, consent_id)
    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
    if consent.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your consent")

    await session.delete(consent)
    await session.commit()

    return {"message": "Consent revoked"}


@router.delete("/client/{client_id}")
async def revoke_client_consent(
    client_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """撤销对指定客户端的所有授权"""
    from app.infrastructure.persistence.models.oauth import UserConsent
    from sqlmodel import select

    result = await session.exec(
        select(UserConsent).where(
            UserConsent.user_id == user_id,
            UserConsent.client_id == client_id,
        )
    )
    consents = result.all()
    for c in consents:
        await session.delete(c)
    await session.commit()

    return {"message": f"Revoked {len(consents)} consent(s)"}