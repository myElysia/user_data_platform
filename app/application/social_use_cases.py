"""社交登录用例 — 授权跳转/回调处理/绑定管理

DDD 应用层：编排社交适配器（infrastructure/social）、OauthProvider 配置、
OauthAccount 绑定与认证用例（风险评估/2FA 挑战共用 post_credential_login）。
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.auth_use_cases import auth_use_cases
from app.application.audit_service import record_audit
from app.domain.identity.services import hash_password
from app.infrastructure.persistence.models import OauthAccount, OauthProvider, OAuthState, User
from app.infrastructure.social import get_adapter
from app.infrastructure.social.base import SocialUserInfo
from app.infrastructure.utils.security import generate_random_string
from app.interface.api.schemas.auth import UserProfile

STATE_PREFIX_BIND = "bind"
STATE_PREFIX_LOGIN = "login"
STATE_TTL = timedelta(minutes=5)
SOCIAL_EMAIL_DOMAIN = "social.local"


def _request_meta(request: Request) -> tuple[str, dict]:
    ip = request.client.host if request.client else "unknown"
    return ip, {"user_agent": request.headers.get("user-agent", "")}


class SocialUseCases:
    """社交账号绑定与登录用例"""

    def __init__(self):
        self.auth = auth_use_cases  # 复用认证用例（风险评估/2FA/会话）

    # ------------------------------------------------------------------
    # 授权跳转
    # ------------------------------------------------------------------

    async def authorize(
        self,
        session: AsyncSession,
        provider_name: str,
        bind: bool,
        request: Request,
        redirect_uri: Optional[str] = None,
    ) -> str:
        """生成 state 并返回第三方平台授权页 URL（302 跳转目标）

        redirect_uri 可选：前端 SSR 模式传入自定回调页（如 /social/github/callback），
        未传时默认后端 /api/v1/auth/social/{provider}/callback。
        """
        provider = await self._get_provider(session, provider_name)
        callback_uri = self._build_redirect_uri(
            request, provider_name, redirect_uri,
        )

        prefix = STATE_PREFIX_BIND if bind else STATE_PREFIX_LOGIN
        state = f"{prefix}_{generate_random_string(32)}"
        session.add(OAuthState(state=state, redirect_uri=callback_uri))
        await session.commit()

        adapter = get_adapter(provider_name)
        return adapter.build_authorize_url(
            provider, state, callback_uri,
        )

    # ------------------------------------------------------------------
    # 回调处理
    # ------------------------------------------------------------------

    async def callback(
        self,
        session: AsyncSession,
        provider_name: str,
        code: str,
        state: str,
        request: Request,
        current_user_id: Optional[int],
    ) -> dict:
        """平台回调：校验 state → 换 token → 拉 userinfo → 绑定或登录"""
        state_row = await session.get(OAuthState, state)
        if state_row is None:
            raise HTTPException(status_code=400, detail="Invalid state")

        is_bind = state.startswith(STATE_PREFIX_BIND)
        await session.delete(state_row)
        await session.commit()

        # OAuthState.created_at 为本地 naive 时间，用同口径比较
        if datetime.now() > state_row.created_at + STATE_TTL:
            raise HTTPException(status_code=400, detail="Expired state")

        provider = await self._get_provider(session, provider_name)
        adapter = get_adapter(provider_name)
        # token 交换必须使用 authorize 时登记的 redirect_uri（与第三方平台校验一致）
        redirect_uri = state_row.redirect_uri

        try:
            access_token = await adapter.exchange_token(provider, code, redirect_uri)
            raw = await adapter.fetch_userinfo(provider, access_token)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Social provider error: {exc}")

        # 平台字段映射（FieldMapping.transform_fields），再归一化
        transformed = await provider.transform_fields(raw, session)
        info = adapter.normalize(transformed)
        if not info.provider_uid:
            raise HTTPException(status_code=400, detail="Provider userinfo missing uid")

        if is_bind:
            return await self._bind_account(
                session, provider, info, access_token, current_user_id, request,
            )
        return await self._login_or_register(
            session, provider, info, access_token, request,
        )

    async def _bind_account(
        self,
        session: AsyncSession,
        provider: OauthProvider,
        info: SocialUserInfo,
        access_token: str,
        current_user_id: Optional[int],
        request: Request,
    ) -> dict:
        """已登录用户绑定第三方账号"""
        if current_user_id is None:
            raise HTTPException(status_code=401, detail="Login required to bind social account")

        existing = await session.exec(
            select(OauthAccount).where(
                OauthAccount.provider_id == provider.id,
                OauthAccount.provider_uid == info.provider_uid,
            )
        )
        if existing.first():
            raise HTTPException(status_code=409, detail="Social account already bound")

        session.add(OauthAccount(
            user_id=current_user_id,
            provider_id=provider.id,
            provider_uid=info.provider_uid,
            verification_token="",
            access_token=access_token,
            refresh_token="",
        ))
        await session.commit()

        ip, meta = _request_meta(request)
        await record_audit(
            session, current_user_id, "social_bound", ip_address=ip,
            request_metadata=meta, operation_type="BIND",
            new_value=f"{provider.name}:{info.provider_uid}",
        )
        return {
            "message": "Social account bound",
            "provider": provider.name,
            "provider_uid": info.provider_uid,
        }

    async def _login_or_register(
        self,
        session: AsyncSession,
        provider: OauthProvider,
        info: SocialUserInfo,
        access_token: str,
        request: Request,
    ) -> dict:
        """未登录：已有绑定则登录，否则注册新用户并绑定"""
        existing = await session.exec(
            select(OauthAccount).where(
                OauthAccount.provider_id == provider.id,
                OauthAccount.provider_uid == info.provider_uid,
            )
        )
        account = existing.first()

        user: Optional[User] = None
        if account is not None:
            user = await session.get(User, account.user_id)
            if user is None:
                raise HTTPException(status_code=404, detail="Bound user not found")
            if not user.is_active:
                raise HTTPException(status_code=403, detail="Account is deactivated")
            account.access_token = access_token
            account.verification_token = account.verification_token or ""
            session.add(account)
            await session.commit()

        if user is None:
            user = await self._register_social_user(
                session, provider, info, access_token, request,
            )

        # 登录统一经过风险评估（第九阶段接入）与 2FA 挑战判定
        outcome = await self.auth.post_credential_login(session, user, request)
        if outcome.mfa_required:
            return {
                "mfa_required": True,
                "mfa_challenge_token": outcome.mfa_challenge_token,
            }
        return {
            "mfa_required": False,
            "user": UserProfile.from_user(outcome.user).model_dump(),
            "access_token": outcome.access_token,
            "refresh_token": outcome.refresh_token,
            "token_type": "Bearer",
            "expires_in": outcome.expires_in,
        }

    async def _register_social_user(
        self,
        session: AsyncSession,
        provider: OauthProvider,
        info: SocialUserInfo,
        access_token: str,
        request: Request,
    ) -> User:
        """注册新用户并绑定社交账号（无邮箱时生成占位邮箱）"""
        email = info.email or f"{provider.name}_{info.provider_uid}@{SOCIAL_EMAIL_DOMAIN}"
        clash = await session.exec(select(User).where(User.email == email))
        if clash.first():
            email = (
                f"{provider.name}_{info.provider_uid}_{secrets.token_hex(4)}"
                f"@{SOCIAL_EMAIL_DOMAIN}"
            )

        user = User(
            email=email,
            password=hash_password(secrets.token_urlsafe(32)),
            display_name=info.display_name or f"{provider.name}_{info.provider_uid}",
            icon=info.avatar_url,
            phone=None,  # phone 唯一约束：空字符串会冲突，用 NULL（SQLite 允许多个 NULL）
            is_active=True,
            email_verified=bool(info.email),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        session.add(OauthAccount(
            user_id=user.id,
            provider_id=provider.id,
            provider_uid=info.provider_uid,
            verification_token="",
            access_token=access_token,
            refresh_token="",
        ))
        await session.commit()

        ip, meta = _request_meta(request)
        await record_audit(
            session, user.id, "social_registered", ip_address=ip,
            request_metadata=meta, operation_type="REGISTER",
            new_value=f"{provider.name}:{info.provider_uid}",
        )
        return user

    # ------------------------------------------------------------------
    # 绑定管理
    # ------------------------------------------------------------------

    async def list_accounts(
        self, session: AsyncSession, user_id: int,
    ) -> list[dict]:
        """列出当前用户绑定的社交账号"""
        result = await session.exec(
            select(OauthAccount).where(OauthAccount.user_id == user_id)
        )
        accounts = result.all()
        output = []
        for account in accounts:
            provider = await session.get(OauthProvider, account.provider_id)
            output.append({
                "id": account.id,
                "provider": provider.name if provider else str(account.provider_id),
                "provider_uid": account.provider_uid,
                "created_at": account.created_at,
            })
        return output

    async def unbind(
        self,
        session: AsyncSession,
        user_id: int,
        account_id: int,
        request: Request,
    ) -> None:
        """解绑社交账号"""
        account = await session.get(OauthAccount, account_id)
        if account is None or account.user_id != user_id:
            raise HTTPException(status_code=404, detail="Social account not found")

        await session.delete(account)
        await session.commit()

        ip, meta = _request_meta(request)
        await record_audit(
            session, user_id, "social_unbound", ip_address=ip,
            request_metadata=meta, operation_type="UNBIND",
            old_value=f"account_id:{account_id}",
        )

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    async def _get_provider(
        self, session: AsyncSession, name: str,
    ) -> OauthProvider:
        result = await session.exec(
            select(OauthProvider).where(
                OauthProvider.name == name,
                OauthProvider.is_active == True,  # noqa: E712
                OauthProvider.deleted_at == None,  # noqa: E711
            )
        )
        provider = result.first()
        if provider is None:
            raise HTTPException(
                status_code=404, detail=f"Provider not found or inactive: {name}",
            )
        return provider

    @staticmethod
    def _build_redirect_uri(
        request: Request,
        provider_name: str,
        redirect_uri: Optional[str] = None,
    ) -> str:
        """回调地址：优先使用显式传入（前端 OAuth 页面模式），否则默认后端 API 回调"""
        if redirect_uri:
            if not (
                redirect_uri.startswith("http://")
                or redirect_uri.startswith("https://")
            ):
                raise HTTPException(
                    status_code=400,
                    detail="redirect_uri must be an absolute http(s) URL",
                )
            return redirect_uri
        base = str(request.base_url).rstrip("/")
        return f"{base}/api/v1/auth/social/{provider_name}/callback"


# 模块级单例
social_use_cases = SocialUseCases()
