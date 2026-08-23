"""验证码请求/响应模型"""

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class VerificationRequest(BaseModel):
    """请求验证码（邮箱验证/手机验证/2FA 备用/风险挑战）

    - channel=email 时必填 email（邮件验证码）
    - channel=phone 时必填 phone（短信验证码）
    """
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    channel: Literal["email", "phone"] = "email"
    purpose: Literal["email_verify", "phone_verify", "2fa_backup", "risk_challenge"] = "email_verify"

    @model_validator(mode="after")
    def _check_target(self):
        if self.channel == "email" and not self.email:
            raise ValueError("email is required when channel is email")
        if self.channel == "phone" and not self.phone:
            raise ValueError("phone is required when channel is phone")
        return self


class VerificationRequestResponse(BaseModel):
    """验证码请求响应（不返回明文验证码）"""
    message: str = "Verification code sent"
    mode: str = "inline"          # 发送模式：queued（ARQ）/inline（进程内降级）
    expires_in: int = 600


class VerificationVerifyRequest(BaseModel):
    """校验验证码（channel 决定目标地址：email 或 phone）"""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    channel: Literal["email", "phone"] = "email"
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    purpose: Literal["email_verify", "phone_verify", "2fa_backup", "risk_challenge"] = "email_verify"

    @model_validator(mode="after")
    def _check_target(self):
        if self.channel == "email" and not self.email:
            raise ValueError("email is required when channel is email")
        if self.channel == "phone" and not self.phone:
            raise ValueError("phone is required when channel is phone")
        return self


class VerificationVerifyResponse(BaseModel):
    """验证码校验响应"""
    verified: bool = True
    purpose: str
