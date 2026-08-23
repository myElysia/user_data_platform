"""认证用例 — 密码登录（含 2FA 挑战）/MFA 管理/会话签发

DDD 应用层：编排领域服务与基础设施，供接口层端点调用。
- password_login：密码验证 → 风险评估（第九阶段接入）→ 2FA 挑战判定
- complete_mfa_login：校验短期挑战令牌 + TOTP 动态码 → 签发正式会话
- setup_totp/confirm_totp/mfa_status/disable_mfa：TOTP 生命周期管理
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.federation.token_service import TokenManager
from app.domain.identity.services import verify_password
from app.domain.security.services import TotpService
from app.infrastructure.persistence.models import (
    DeviceFingerprint, MFASecuity, SSOSession, User,
)

ACCESS_TOKEN_TTL = timedelta(hours=24)
REFRESH_TOKEN_TTL = timedelta(days=30)
REMEMBER_ME_TTL = timedelta(days=7)
MFA_CHALLENGE_TTL = timedelta(minutes=10)
MFA_CHALLENGE_PURPOSE = "mfa_login"
MFA_METHOD_TOTP = "TOTP"
LOGIN_FAIL_KEY_PREFIX = "login_fail"
LOGIN_FAIL_WINDOW_SECONDS = 900  # 15 分钟失败计数窗口


@dataclass
class LoginOutcome:
    """登录结果 — 2FA 挑战（mfa_required=True）或认证成功二选一"""

    mfa_required: bool = False
    mfa_challenge_token: Optional[str] = None
    challenge_method: Optional[str] = None  # "totp" / "email_code"（风险挑战）
    user: Optional[User] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None


class AuthUseCases:
    """认证用例编排"""

    def __init__(self):
        self.totp = TotpService()
        self.token_manager = TokenManager()

    # ------------------------------------------------------------------
    # 会话签发
    # ------------------------------------------------------------------

    async def create_session(
        self,
        session: AsyncSession,
        user: User,
        request: Request,
        remember_me: bool = False,
    ) -> tuple[str, str, int]:
        """创建 SSO 会话，返回 (access_token, refresh_token, expires_in)"""
        access_ttl = REMEMBER_ME_TTL if remember_me else ACCESS_TOKEN_TTL

        access_token, _, at_exp = self.token_manager.issue_access_token(
            sub=str(user.id),
            client_id="user_platform",
            scopes=["openid", "profile", "email"],
            ttl=access_ttl,
        )
        refresh_token, _, _ = self.token_manager.issue_refresh_token(sub=str(user.id))

        device_fp = SSOSession.generate_device_fingerprint(request)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        sso = SSOSession(
            user_id=user.id,
            session_token=access_token,
            refresh_token=refresh_token,
            expires_at=at_exp,
            device_fingerprint=device_fp,
            ip_address=client_ip,
            user_agent=user_agent[:300],
        )
        session.add(sso)
        await session.commit()

        # 第八阶段：设备指纹写入/更新
        await self._upsert_device(session, user.id, device_fp, request)

        return access_token, refresh_token, int(access_ttl.total_seconds())

    # ------------------------------------------------------------------
    # 密码登录（含 2FA 挑战判定）
    # ------------------------------------------------------------------

    async def password_login(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        request: Request,
        remember_me: bool = False,
    ) -> LoginOutcome:
        """密码登录第一步：凭证校验 → 风险评估 → 2FA 挑战判定"""
        result = await session.exec(select(User).where(User.email == email))
        user = result.first()
        if not user:
            await self._record_login_failure(email)
            await self._audit(session, 0, "login_failed", request,
                              new_value=f"unknown_email:{email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated")

        if not user.password or not verify_password(password, user.password):
            await self._record_login_failure(email)
            await self._audit(session, user.id, "login_failed", request)
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return await self.post_credential_login(
            session, user, request, remember_me=remember_me,
        )

    async def post_credential_login(
        self,
        session: AsyncSession,
        user: User,
        request: Request,
        remember_me: bool = False,
    ) -> LoginOutcome:
        """凭证验证通过后的登录流：风险评估 → 2FA 挑战判定 → 会话签发

        密码登录与社交登录共用本流程（计划要求登录统一经过风险评估）。
        """
        risk_action = await self.assess_login_risk(session, user, request)

        if risk_action == "BLOCK":
            await self._audit(session, user.id, "risk_blocked", request)
            raise HTTPException(
                status_code=403, detail="Login blocked by risk engine",
            )

        mfa = await self._get_active_totp(session, user.id)
        if mfa is not None or risk_action == "CHALLENGE_2FA":
            challenge_method = "totp"
            if mfa is None:
                # 中风险且未启用 TOTP → 自动发送邮箱验证码挑战
                ip = request.client.host if request.client else "unknown"
                from app.application.verification_use_cases import (
                    verification_use_cases,
                )
                await verification_use_cases.request_code(
                    session, user.email or "", "risk_challenge", ip,
                )
                challenge_method = "email_code"
            return LoginOutcome(
                mfa_required=True,
                mfa_challenge_token=self.issue_mfa_challenge(user, remember_me),
                challenge_method=challenge_method,
            )

        access_token, refresh_token, expires_in = await self.create_session(
            session, user, request, remember_me=remember_me,
        )
        await self._clear_login_failure(user.email)
        await self._audit(session, user.id, "login_success", request)
        return LoginOutcome(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    def issue_mfa_challenge(self, user: User, remember_me: bool = False) -> str:
        """签发短期 MFA 挑战令牌（10 分钟，用途 mfa_login）"""
        challenge_token, _, _ = self.token_manager.issue_short_lived_token(
            sub=str(user.id),
            purpose=MFA_CHALLENGE_PURPOSE,
            ttl=MFA_CHALLENGE_TTL,
            email=user.email or "",
            remember_me=remember_me,
        )
        return challenge_token

    async def assess_login_risk(
        self, session: AsyncSession, user: User, request: Request,
    ) -> Optional[str]:
        """登录风险评估（第九阶段：RiskAssessmentService 规则引擎 + RiskEvent 落库）

        返回 "ALLOW" / "CHALLENGE_2FA" / "BLOCK"。
        """
        from app.application.risk_use_cases import risk_use_cases
        return await risk_use_cases.assess_login(session, user, request)

    async def complete_mfa_login(
        self,
        session: AsyncSession,
        challenge_token: str,
        code: str,
        request: Request,
    ) -> LoginOutcome:
        """登录第二步：校验 MFA 挑战令牌 + TOTP 动态码，签发正式会话"""
        from jose import JWTError

        try:
            claims = self.token_manager.verify_purpose_token(
                challenge_token, MFA_CHALLENGE_PURPOSE,
            )
        except JWTError:
            raise HTTPException(
                status_code=401, detail="Invalid or expired challenge token",
            )

        user_id = int(claims.get("sub", 0))
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        mfa = await self._get_active_totp(session, user_id)
        if mfa is None:
            # 无 TOTP → 中风险邮箱验证码挑战（risk_challenge）
            from app.application.verification_use_cases import (
                verification_use_cases,
            )
            try:
                await verification_use_cases.verify_code(
                    session, user.email or "", code, "risk_challenge",
                )
            except HTTPException:
                await self._audit(session, user_id, "mfa_login_failed", request)
                raise
        elif not self.totp.verify(mfa.secret, code):
            await self._audit(session, user_id, "mfa_login_failed", request)
            raise HTTPException(status_code=401, detail="Invalid TOTP code")

        if mfa is not None:
            mfa.last_used = datetime.now(timezone.utc)
            session.add(mfa)
            await session.commit()

        remember_me = bool(claims.get("remember_me"))
        access_token, refresh_token, expires_in = await self.create_session(
            session, user, request, remember_me=remember_me,
        )
        await self._clear_login_failure(user.email)
        await self._audit(session, user_id, "mfa_login_success", request)

        return LoginOutcome(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    # ------------------------------------------------------------------
    # TOTP 生命周期管理
    # ------------------------------------------------------------------

    async def setup_totp(
        self, session: AsyncSession, user: User,
    ) -> tuple[str, str]:
        """生成 TOTP secret 与 otpauth URI（未激活，待 confirm 校验后启用）"""
        existing = await session.exec(
            select(MFASecuity).where(
                MFASecuity.user_id == user.id,
                MFASecuity.method_type == MFA_METHOD_TOTP,
            )
        )
        row = existing.first()
        if row is not None and row.is_active:
            raise HTTPException(status_code=409, detail="TOTP is already enabled")

        secret = self.totp.generate_secret()
        uri = self.totp.build_uri(secret, user.email or str(user.id))

        if row is not None:
            row.secret = secret
            row.is_active = False
            session.add(row)
        else:
            session.add(MFASecuity(
                user_id=user.id,
                method_type=MFA_METHOD_TOTP,
                secret=secret,
                is_active=False,
            ))
        await session.commit()

        return secret, uri

    async def confirm_totp(
        self,
        session: AsyncSession,
        user: User,
        code: str,
        request: Request,
    ) -> None:
        """校验动态码后启用 TOTP"""
        pending = await session.exec(
            select(MFASecuity).where(
                MFASecuity.user_id == user.id,
                MFASecuity.method_type == MFA_METHOD_TOTP,
                MFASecuity.is_active == False,  # noqa: E712
            )
        )
        row = pending.first()
        if row is None:
            raise HTTPException(status_code=404, detail="No pending TOTP setup found")

        if not self.totp.verify(row.secret, code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        row.is_active = True
        row.last_used = None
        session.add(row)
        await session.commit()

        await self._audit(session, user.id, "mfa_enabled", request)

    async def mfa_status(self, session: AsyncSession, user: User) -> dict:
        """查询 MFA 开关状态"""
        row = await self._get_active_totp(session, user.id)
        if row is None:
            return {"enabled": False, "method": None, "last_used": None}
        return {
            "enabled": True,
            "method": row.method_type,
            "last_used": row.last_used,
        }

    async def disable_mfa(
        self,
        session: AsyncSession,
        user: User,
        password: Optional[str],
        code: Optional[str],
        request: Request,
    ) -> None:
        """禁用 MFA — 需验证当前密码或 TOTP 动态码"""
        row = await self._get_active_totp(session, user.id)
        if row is None:
            raise HTTPException(status_code=404, detail="TOTP is not enabled")

        validated = False
        if password and user.password and verify_password(password, user.password):
            validated = True
        elif code and self.totp.verify(row.secret, code):
            validated = True

        if not validated:
            raise HTTPException(
                status_code=400,
                detail="Current password or TOTP code required to disable MFA",
            )

        row.is_active = False
        session.add(row)
        await session.commit()

        await self._audit(session, user.id, "mfa_disabled", request)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    async def _get_active_totp(
        self, session: AsyncSession, user_id: int,
    ) -> Optional[MFASecuity]:
        result = await session.exec(
            select(MFASecuity).where(
                MFASecuity.user_id == user_id,
                MFASecuity.method_type == MFA_METHOD_TOTP,
                MFASecuity.is_active == True,  # noqa: E712
            )
        )
        return result.first()

    async def _record_login_failure(self, email: str) -> None:
        """登录失败计数写入缓存（供第九阶段风险引擎使用）"""
        from app.infrastructure.cache import get_cache_backend

        backend = await get_cache_backend()
        key = f"{LOGIN_FAIL_KEY_PREFIX}:{email}"
        count = int(await backend.get(key) or 0) + 1
        await backend.setex(key, LOGIN_FAIL_WINDOW_SECONDS, count)

    async def _clear_login_failure(self, email: str) -> None:
        """登录成功后清除失败计数（避免成功登录仍被风险引擎加分）"""
        from app.infrastructure.cache import get_cache_backend

        backend = await get_cache_backend()
        await backend.delete(f"{LOGIN_FAIL_KEY_PREFIX}:{email}")

    async def _upsert_device(
        self,
        session: AsyncSession,
        user_id: int,
        fp: str,
        request: Request,
    ) -> None:
        """创建或更新设备指纹记录（第八阶段：设备指纹绑定）"""
        result = await session.exec(
            select(DeviceFingerprint).where(
                DeviceFingerprint.fingerprint_hash == fp,
            )
        )
        device = result.first()
        now = datetime.now(timezone.utc)

        if device is not None:
            if device.user_id != user_id:
                device.user_id = user_id  # 设备归属变更
            device.verification_count += 1
            device.last_seen = now
            session.add(device)
        else:
            session.add(DeviceFingerprint(
                user_id=user_id,
                fingerprint_hash=fp,
                verification_count=1,  # 首次登录即第 1 次验证
                device_info={
                    "ua": request.headers.get("user-agent", ""),
                    "accept_language": request.headers.get("accept-language", ""),
                    "sec_ch_ua": request.headers.get("sec-ch-ua", ""),
                },
                first_seen=now,
                last_seen=now,
            ))
        await session.commit()

    async def _audit(
        self, session: AsyncSession, user_id: int, action: str, request: Request,
        new_value: Optional[str] = None,
    ) -> None:
        from app.application.audit_service import record_audit

        ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        await record_audit(
            session,
            user_id=user_id,
            action=action,
            ip_address=ip,
            request_metadata={"user_agent": user_agent},
            new_value=new_value,
        )


# 模块级单例（端点注入使用）
auth_use_cases = AuthUseCases()
