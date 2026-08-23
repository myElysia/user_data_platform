from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Boolean, DateTime, Integer, func
from sqlmodel import Field, Relationship, SQLModel

from app.infrastructure.config.app import AppSettings

app_settings = AppSettings()


class UserMixin(SQLModel):
    icon: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None


class User(UserMixin, table=True, table_description="用户表"):
    __tablename__ = f"{app_settings.APP_NAME}_user"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    email: Optional[str] = Field("", max_length=255, nullable=False, unique=True, title="邮箱")
    country: Optional[str] = Field("China", max_length=100, nullable=False, title="国家")
    language: Optional[str] = Field("zh-CN", nullable=False, title="语言配置")
    phone: Optional[str] = Field(None, max_length=255, nullable=True, unique=True, title="电话")
    display_name: Optional[str] = Field("", max_length=50, nullable=True, title="个人昵称")
    is_active: bool = Field(True, sa_column=Column(Boolean, nullable=False), title="是否激活")
    created_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False),
                                 title="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  onupdate=func.now(),
                                                  nullable=False),
                                 title="更新时间")
    deleted_at: datetime = Field(default=None,
                                 sa_column=Column(DateTime(timezone=True),
                                                  nullable=True),
                                 title="删除时间")
    # 用户验证相关
    email_verified: bool = False
    phone_verified: bool = False
    # 以下是外键列表
    # SSO_Session
    sso_sessions: List["SSOSession"] = Relationship(back_populates="user")
    # MFA认证, 支持短信/MAIL
    mfa_secuity: List["MFASecuity"] = Relationship(back_populates="user")
    # oauth_accounts
    oauth_accounts: List["OauthAccount"] = Relationship(back_populates="user")
    # OAuth 客户端（所有者）
    oauth_clients: List["OAuthClient"] = Relationship(back_populates="owner")
    # OAuth 同意记录
    oauth_consents: List["UserConsent"] = Relationship(back_populates="user")
    # 审计日志
    audit_logs: List["AuditLog"] = Relationship(back_populates="user")

    # 去除密码字段,仅在模型中可读写
    model_config = {
        "exclude": ["password"]
    }

