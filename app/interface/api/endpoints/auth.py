"""用户认证端点 — 注册、登录、登出、资料管理"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.auth_use_cases import auth_use_cases
from app.interface.api.deps.auth import get_current_token, get_current_user_id
from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models import User, SSOSession
from app.interface.api.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    ChangePasswordRequest,
    ProfileUpdateRequest,
    AuthResponse,
    LoginResponse,
    UserProfile,
)
from app.domain.identity.services import hash_password, verify_password
from app.domain.identity.services import PasswordPolicy

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """用户注册

    - 邮箱唯一性校验
    - 密码强度校验（大小写 + 数字 + 特殊字符）
    - 自动创建 SSO 会话
    """
    # 校验密码强度
    PasswordPolicy.validate(body.password)

    # 可选邮箱验证码：提供则先校验（email_verify 场景）
    if body.email_code:
        from app.application.verification_use_cases import verification_use_cases
        await verification_use_cases.verify_code(
            session, body.email, body.email_code, "email_verify",
        )

    # 检查邮箱是否已注册
    existing = await session.exec(
        select(User).where(User.email == body.email)
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="Email already registered")

    # 创建用户
    user = User(
        email=body.email,
        password=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
        country=body.country,
        language=body.language,
        phone=None,  # phone 唯一约束：空字符串会冲突，用 NULL（SQLite 允许多个 NULL）
        email_verified=bool(body.email_code),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # 创建会话
    access_token, refresh_token, expires_in = await auth_use_cases.create_session(
        session, user, request,
    )

    return AuthResponse(
        user=UserProfile.from_user(user),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """用户登录

    支持邮箱 + 密码登录。密码验证通过后：
    - 用户启用 2FA（或风险评估为中风险）→ 返回 mfa_required + mfa_challenge_token
    - 否则直接签发 JWT 会话令牌
    """
    outcome = await auth_use_cases.password_login(
        session, body.email, body.password, request, body.remember_me,
    )

    if outcome.mfa_required:
        return LoginResponse(
            mfa_required=True,
            mfa_challenge_token=outcome.mfa_challenge_token,
        )

    return LoginResponse(
        user=UserProfile.from_user(outcome.user),
        access_token=outcome.access_token,
        refresh_token=outcome.refresh_token,
        expires_in=outcome.expires_in,
    )


# ---------------------------------------------------------------------------
# 登出
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout(
    request: Request,
    claims: dict = Depends(get_current_token),
    session: AsyncSession = Depends(get_db_session),
):
    """用户登出 — 撤销当前会话令牌"""
    jti = claims.get("jti")
    if jti:
        result = await session.exec(
            select(SSOSession).where(
                SSOSession.session_token == jti,
                SSOSession.is_active == True,
            )
        )
        sso = result.first()
        if sso:
            sso.is_active = False
            session.add(sso)
            await session.commit()

    return {"message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# 刷新令牌
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """刷新会话令牌 — 使用 refresh_token 换取新的 access_token"""
    from app.domain.federation.token_service import TokenManager
    from jose import JWTError

    token_manager = TokenManager()

    # 从 Authorization header 获取 refresh_token
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing refresh token")

    refresh_token_str = auth[7:]

    try:
        claims = token_manager.verify(refresh_token_str)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # refresh_token（携带 sub）与未过期的 access_token 均可换取新会话
    if claims.get("token_type") not in ("Bearer", "refresh_token"):
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = int(claims.get("sub", 0))
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 撤销旧会话
    jti = claims.get("jti")
    if jti:
        result = await session.exec(
            select(SSOSession).where(SSOSession.session_token == jti)
        )
        old_sso = result.first()
        if old_sso:
            old_sso.is_active = False
            session.add(old_sso)

    # 创建新会话
    access_token, refresh_token, expires_in = await auth_use_cases.create_session(
        session, user, request,
    )

    return AuthResponse(
        user=UserProfile.from_user(user),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


# ---------------------------------------------------------------------------
# 获取当前用户资料
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=UserProfile)
async def get_profile(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """获取当前登录用户的个人资料"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile.from_user(user)


# ---------------------------------------------------------------------------
# 更新个人资料
# ---------------------------------------------------------------------------

@router.put("/profile", response_model=UserProfile)
async def update_profile(
    body: ProfileUpdateRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """更新当前用户的个人资料"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserProfile.from_user(user)


# ---------------------------------------------------------------------------
# 修改密码
# ---------------------------------------------------------------------------

@router.put("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """修改当前用户密码"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 验证旧密码
    if not user.password or not verify_password(body.old_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # 校验新密码强度
    PasswordPolicy.validate(body.new_password)

    # 更新密码
    user.password = hash_password(body.new_password)
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    await session.commit()

    # 审计：密码修改（不记录密码内容）
    from app.application.audit_service import record_audit
    ip = request.client.host if request.client else "unknown"
    await record_audit(
        session, user_id, "password_changed", ip_address=ip,
        request_metadata={"user_agent": request.headers.get("user-agent", "")},
    )

    return {"message": "Password changed successfully"}