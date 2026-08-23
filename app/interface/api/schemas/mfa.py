"""MFA（双因素认证）请求/响应模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TotpSetupResponse(BaseModel):
    """TOTP 绑定初始化响应 — secret 供客户端生成二维码，尚未激活"""
    secret: str
    otpauth_uri: str


class TotpConfirmRequest(BaseModel):
    """TOTP 绑定确认请求 — 提交当前动态码以激活"""
    code: str = Field(..., min_length=6, max_length=8, description="6 位 TOTP 动态码")


class MfaStatusResponse(BaseModel):
    """MFA 状态响应"""
    enabled: bool
    method: Optional[str] = None
    last_used: Optional[datetime] = None


class MfaDisableRequest(BaseModel):
    """禁用 MFA 请求 — 需验证当前密码或 TOTP 动态码（二选一）"""
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    code: Optional[str] = Field(None, min_length=6, max_length=8)


class MfaLoginRequest(BaseModel):
    """登录第二步请求 — 提交 MFA 挑战令牌与 TOTP 动态码"""
    mfa_challenge_token: str
    code: str = Field(..., min_length=6, max_length=8, description="6 位 TOTP 动态码")
