from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import Column, Boolean, DateTime, String, Integer, func
from sqlalchemy_utils import StringEncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import FernetEngine
from sqlmodel import Field, Relationship, SQLModel

from app.local.settings import Settings

settings = Settings()


class UserRole(str, Enum):
    ADMIN = "admin"
    GUEST = "guest"
    USER = "user"


class UserMixin(SQLModel):
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None
    hash_password: Optional[str] = None
    # 用户权限, 只有admin/guest 支持访问后台
    role: UserRole = Field(UserRole.USER)


class User(UserMixin, table=True, table_description="用户表"):
    __tablename__ = f"{settings.APP_NAME}_user"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    username: Optional[str] = Field("", max_length=50, nullable=False, unique=True, title="用户名")
    email: Optional[str] = Field("", max_length=255, nullable=False, unique=True, title="邮箱")
    country: Optional[str] = Field("China", max_length=100, nullable=False, title="国家")
    language: Optional[str] = Field("zh-CN", nullable=False, title="语言配置")
    phone: Optional[str] = Field("", max_length=255, nullable=True, unique=True, title="电话")
    display_name: Optional[str] = Field("", max_length=50, nullable=True, title="个人昵称")
    hash_password: str = Field("", max_length=255, nullable=False, title="密码")
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
    oauth_accounts: List["OauthAccount"] = Relationship(back_populates="user")
    verifications: List["UserVerification"] = Relationship(back_populates="user")
    sso_sessions: List["SSOSession"] = Relationship(back_populates="user")
    audit_logs: List["AuditLog"] = Relationship(back_populates="user")
    mfa_methods: List["MFAMethod"] = Relationship(back_populates="user")
    # 以下是用户多对多关系列表

    # 去除密码字段,仅在模型中可读写
    model_config = {
        "exclude": ["password"]
    }


class VerificationType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"


class UserVerification(SQLModel, table=True, table_description="邮箱验证码"):
    __tablename__ = f"{settings.APP_NAME}_user_verification"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    user: User = Relationship(back_populates="verifications")
    user_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_user.id", title="关联用户ID")  # 必须绑定用户
    verify_type: VerificationType = Field(VerificationType.EMAIL)
    code: str = Field(..., max_length=500, title="验证码",
                      sa_column=Column(StringEncryptedType(
                          type_in=String,
                          key=settings.SECRET_KEY,
                          engine=FernetEngine),
                          unique=True
                      ))
    attempts: int = Field(0, title="尝试次数")
