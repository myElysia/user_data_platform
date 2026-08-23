"""认证相关请求/响应模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """用户注册请求"""
    email: str = Field(..., max_length=255, pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field("", max_length=50)
    country: str = Field("China", max_length=100)
    language: str = Field("zh-CN", max_length=20)
    email_code: Optional[str] = Field(None, min_length=6, max_length=6,
                                      pattern=r"^\d{6}$",
                                      description="可选：邮箱验证码，提供则先校验")


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """用户登录请求"""
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)
    remember_me: bool = Field(False, description="是否延长会话有效期")


# ---------------------------------------------------------------------------
# 修改密码
# ---------------------------------------------------------------------------

class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# 更新资料
# ---------------------------------------------------------------------------

class ProfileUpdateRequest(BaseModel):
    """更新个人资料请求"""
    display_name: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=255)
    language: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# 认证响应
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    """用户资料"""
    id: int
    email: str
    display_name: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    icon: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False
    is_active: bool = True
    created_at: datetime

    @classmethod
    def from_user(cls, user) -> "UserProfile":
        """从 User 模型构建资料视图"""
        return cls(
            id=user.id,
            email=user.email or "",
            display_name=user.display_name,
            phone=user.phone,
            country=user.country,
            language=user.language,
            icon=user.icon,
            email_verified=user.email_verified,
            phone_verified=user.phone_verified,
            is_active=user.is_active,
            created_at=user.created_at,
        )


class AuthResponse(BaseModel):
    """认证成功响应"""
    user: UserProfile
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int


class LoginResponse(BaseModel):
    """登录响应 — 2FA 挑战（mfa_required=true）或认证结果二选一"""
    mfa_required: bool = False
    mfa_challenge_token: Optional[str] = None
    user: Optional[UserProfile] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: Optional[int] = None


class LogoutResponse(BaseModel):
    """登出响应"""
    message: str = "Logged out successfully"