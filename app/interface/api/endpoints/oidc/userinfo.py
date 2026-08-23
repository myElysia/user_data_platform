"""OIDC UserInfo 端点 — GET /userinfo"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.interface.api.deps.auth import get_current_token
from app.domain.federation.token_service import ClaimsBuilder
from app.infrastructure.database import get_db_session
from app.interface.api.schemas.oidc import UserInfoResponse

router = APIRouter(tags=["OIDC UserInfo"])


@router.get("/userinfo", response_model=UserInfoResponse)
async def userinfo(
    claims: dict = Depends(get_current_token),
    session: AsyncSession = Depends(get_db_session),
):
    """UserInfo Endpoint — 返回当前用户信息

    需要有效的 Bearer access_token。
    """
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing sub claim")

    # 解析 scope
    scope_str = claims.get("scope", "openid")
    scopes = scope_str.split() if isinstance(scope_str, str) else scope_str

    # 查询用户
    from app.infrastructure.persistence.models import User
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 构建 UserInfo claims
    info = ClaimsBuilder.build_userinfo_claims(user, scopes)
    return info


@router.post("/userinfo")
async def userinfo_post(
    claims: dict = Depends(get_current_token),
    session: AsyncSession = Depends(get_db_session),
):
    """UserInfo Endpoint (POST) — 与 GET 相同"""
    return await userinfo(claims, session)