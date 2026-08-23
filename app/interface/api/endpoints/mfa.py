"""MFA 端点 — TOTP 绑定/启用/禁用/状态查询 + 登录第二步

路由前缀 /api/v1/auth：
- POST   /mfa/totp/setup   初始化绑定（返回 secret + otpauth URI，未激活）
- POST   /mfa/totp/confirm 校验动态码后启用
- DELETE /mfa              禁用（需当前密码或 TOTP）
- GET    /mfa/status       查询开关状态
- POST   /login/mfa        登录第二步（mfa_challenge_token + TOTP code）
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.auth_use_cases import auth_use_cases
from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models import User
from app.interface.api.deps.auth import get_current_user_id
from app.interface.api.schemas.auth import LoginResponse, UserProfile
from app.interface.api.schemas.mfa import (
    MfaDisableRequest,
    MfaLoginRequest,
    MfaStatusResponse,
    TotpConfirmRequest,
    TotpSetupResponse,
)

router = APIRouter(prefix="/v1/auth", tags=["MFA"])


async def _require_user(
    user_id: int, session: AsyncSession,
) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/mfa/totp/setup", response_model=TotpSetupResponse)
async def setup_totp(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """初始化 TOTP 绑定 — 返回 secret 与 otpauth URI（扫码绑定，尚未激活）"""
    user = await _require_user(user_id, session)
    secret, otpauth_uri = await auth_use_cases.setup_totp(session, user)
    return TotpSetupResponse(secret=secret, otpauth_uri=otpauth_uri)


@router.post("/mfa/totp/confirm")
async def confirm_totp(
    body: TotpConfirmRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """校验当前动态码后启用 TOTP"""
    user = await _require_user(user_id, session)
    await auth_use_cases.confirm_totp(session, user, body.code, request)
    return {"message": "TOTP enabled successfully"}


@router.get("/mfa/status", response_model=MfaStatusResponse)
async def mfa_status(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """查询当前用户 MFA 开关状态"""
    user = await _require_user(user_id, session)
    status = await auth_use_cases.mfa_status(session, user)
    return MfaStatusResponse(**status)


@router.delete("/mfa")
async def disable_mfa(
    body: MfaDisableRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """禁用 MFA — 需验证当前密码或 TOTP 动态码"""
    user = await _require_user(user_id, session)
    await auth_use_cases.disable_mfa(
        session, user, body.password, body.code, request,
    )
    return {"message": "MFA disabled successfully"}


@router.post("/login/mfa", response_model=LoginResponse)
async def login_mfa(
    body: MfaLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """登录第二步 — 校验 MFA 挑战令牌与 TOTP 动态码，签发正式会话"""
    outcome = await auth_use_cases.complete_mfa_login(
        session, body.mfa_challenge_token, body.code, request,
    )
    return LoginResponse(
        user=UserProfile.from_user(outcome.user),
        access_token=outcome.access_token,
        refresh_token=outcome.refresh_token,
        expires_in=outcome.expires_in,
    )
