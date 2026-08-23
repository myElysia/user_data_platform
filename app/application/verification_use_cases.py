"""验证码用例 — 请求（限流+入队异步发送）/校验（标记已验证或挑战通过）

第七阶段：ARQ 验证码异步发送。验证码 bcrypt 哈希落库（VerificationCode），
发送经 dispatcher 入队（Redis 不可用自动降级进程内执行）。
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.identity.services import hash_password, verify_password
from app.infrastructure.persistence.models import User, VerificationCode

VALID_PURPOSES = ("email_verify", "phone_verify", "2fa_backup", "risk_challenge")
CODE_TTL = timedelta(minutes=10)
CODE_LENGTH = 6
MAX_ATTEMPTS = 5
RATE_WINDOW_SECONDS = 60       # 同一 IP+邮箱 60 秒一次
DAILY_LIMIT = 10               # 同一 IP+邮箱每日上限
RATE_KEY_PREFIX = "verif_rate"
DAILY_KEY_PREFIX = "verif_daily"


def _generate_code() -> str:
    """生成 6 位数字验证码"""
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


def _rate_keys(ip: str, email: str) -> tuple[str, str]:
    return f"{RATE_KEY_PREFIX}:{ip}:{email}", f"{DAILY_KEY_PREFIX}:{ip}:{email}"


class VerificationUseCases:
    """验证码请求与校验用例"""

    async def request_code(
        self,
        session: AsyncSession,
        email: str,
        purpose: str,
        ip: str,
        channel: str = "email",
    ) -> dict:
        """生成验证码 → 哈希落库 → 入队异步发送（含限流）

        channel 指定发送通道："email"（邮件）或 "phone"（短信）。
        目标地址统一存 email 字段（phone 通道时存手机号），purpose 区分场景。
        """
        if purpose not in VALID_PURPOSES:
            raise HTTPException(status_code=400, detail="Invalid purpose")
        if channel not in ("email", "phone"):
            raise HTTPException(status_code=400, detail="Invalid channel")

        # 限流：60 秒一次 + 每日上限
        from app.infrastructure.cache import get_cache_backend
        backend = await get_cache_backend()
        rate_key, daily_key = _rate_keys(ip, email)

        recent = await backend.get(rate_key)
        if recent:
            raise HTTPException(
                status_code=429,
                detail=f"Too frequent, retry after {RATE_WINDOW_SECONDS}s",
            )

        daily = int(await backend.get(daily_key) or 0)
        if daily >= DAILY_LIMIT:
            raise HTTPException(status_code=429, detail="Daily limit exceeded")

        code = _generate_code()
        code_hash = hash_password(code)
        session.add(VerificationCode(
            email=email,
            code_hash=code_hash,
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + CODE_TTL,
        ))
        await session.commit()

        # 入队异步发送（Redis 不可用自动降级进程内执行）
        from app.infrastructure.messaging.dispatcher import dispatcher
        if channel == "phone":
            mode = await dispatcher.enqueue("send_phone_verification", email, code, purpose)
        else:
            mode = await dispatcher.enqueue("send_verification_email", email, code, purpose)

        # 限流计数
        day = datetime.now().strftime("%Y%m%d")
        await backend.setex(rate_key, RATE_WINDOW_SECONDS, 1)
        await backend.setex(f"{daily_key}:{day}", 86400, daily + 1)

        return {"message": "Verification code sent", "mode": mode,
                "expires_in": int(CODE_TTL.total_seconds())}

    async def verify_code(
        self,
        session: AsyncSession,
        email: str,
        code: str,
        purpose: str,
    ) -> dict:
        """校验验证码 — 成功标记已使用；email_verify 场景标记邮箱已验证"""
        if purpose not in VALID_PURPOSES:
            raise HTTPException(status_code=400, detail="Invalid purpose")

        result = await session.exec(
            select(VerificationCode)
            .where(
                VerificationCode.email == email,
                VerificationCode.purpose == purpose,
                VerificationCode.used_at == None,  # noqa: E711
            )
            .order_by(VerificationCode.id.desc())
        )
        row = result.first()
        if row is None:
            raise HTTPException(status_code=404, detail="No pending verification code")

        # SQLite 读回可能为 naive datetime（无 tzinfo），统一视为 UTC 比较
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Verification code expired")

        if row.attempts >= MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many attempts")

        if not verify_password(code, row.code_hash):
            row.attempts += 1
            session.add(row)
            await session.commit()
            raise HTTPException(status_code=400, detail="Invalid verification code")

        row.used_at = datetime.now(timezone.utc)
        session.add(row)
        await session.commit()

        # email_verify 场景：标记用户邮箱已验证
        if purpose == "email_verify":
            user_result = await session.exec(
                select(User).where(User.email == email)
            )
            user = user_result.first()
            if user is not None and not user.email_verified:
                user.email_verified = True
                session.add(user)
                await session.commit()

        # phone_verify 场景：标记用户手机号已验证
        if purpose == "phone_verify":
            user_result = await session.exec(
                select(User).where(User.phone == email)
            )
            user = user_result.first()
            if user is not None and not user.phone_verified:
                user.phone_verified = True
                session.add(user)
                await session.commit()

        return {"verified": True, "purpose": purpose}


# 模块级单例
verification_use_cases = VerificationUseCases()
