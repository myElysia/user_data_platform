"""验证码端点 — 请求（限流 + ARQ 异步发送）/ 校验

路由前缀 /api/v1/verification：
- POST /request  生成验证码 → bcrypt 落库 → dispatcher 入队发送（60s/每日限流）
- POST /verify   校验验证码 → email_verify 场景标记邮箱已验证
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.verification_use_cases import verification_use_cases
from app.infrastructure.database import get_db_session
from app.interface.api.schemas.verification import (
    VerificationRequest,
    VerificationRequestResponse,
    VerificationVerifyRequest,
    VerificationVerifyResponse,
)

router = APIRouter(prefix="/v1/verification", tags=["Verification"])


@router.post("/request", response_model=VerificationRequestResponse)
async def request_verification(
    body: VerificationRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """请求验证码 — 按 IP+目标地址限流（60 秒一次、每日上限），入队 ARQ 异步发送"""
    ip = request.client.host if request.client else "unknown"
    target = body.email if body.channel == "email" else body.phone
    return await verification_use_cases.request_code(
        session, target, body.purpose, ip, channel=body.channel,
    )


@router.post("/verify", response_model=VerificationVerifyResponse)
async def verify_verification(
    body: VerificationVerifyRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """校验验证码 — email_verify/phone_verify 场景同时标记对应用户已验证"""
    target = body.email if body.channel == "email" else body.phone
    return await verification_use_cases.verify_code(
        session, target, body.code, body.purpose,
    )
