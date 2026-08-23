"""OAuth 2.0 / OIDC 数据模型 — 客户端注册、Scope、同意、Token、设备指纹"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, DateTime, func,
    Boolean, JSON, Text, Float,
)
from sqlalchemy_utils import StringEncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import FernetEngine
from sqlmodel import SQLModel, Field, Relationship

from app.infrastructure.config.app import AppSettings

app_settings = AppSettings()


# ---------------------------------------------------------------------------
# 枚举类型
# ---------------------------------------------------------------------------

class GrantTypeEnum(str, Enum):
    """OAuth 2.0 授权类型"""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"
    IMPLICIT = "implicit"


class TokenTypeEnum(str, Enum):
    """Token 类型"""
    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"
    ID_TOKEN = "id_token"


class ClientAuthMethod(str, Enum):
    """客户端认证方式"""
    CLIENT_SECRET_BASIC = "client_secret_basic"
    CLIENT_SECRET_POST = "client_secret_post"
    NONE = "none"


# ---------------------------------------------------------------------------
# OAuth 客户端
# ---------------------------------------------------------------------------

class OAuthClient(SQLModel, table=True, table_description="OAuth 客户端注册"):
    """OAuth 2.0 客户端 — 类似 GitHub OAuth Apps"""
    __tablename__ = f"{app_settings.APP_NAME}_oauth_client"

    id: int = Field(
        ..., sa_column=Column(Integer, autoincrement=True, primary_key=True),
    )
    client_id: str = Field(
        ..., max_length=64, unique=True, index=True,
        description="客户端唯一标识",
    )
    client_secret: str = Field(
        ..., max_length=500,
        sa_column=Column(
            StringEncryptedType(
                type_in=String,
                key=app_settings.SECRET_KEY,
                engine=FernetEngine,
            ),
            nullable=False,
        ),
        description="客户端密钥（加密存储）",
    )
    name: str = Field(..., max_length=100, description="应用名称")
    description: Optional[str] = Field(
        None, max_length=500, sa_column=Column(Text, nullable=True),
        description="应用描述",
    )

    # 回调 URL 列表
    callback_urls: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
        description="允许的回调 URL 列表",
    )

    # 所有者
    owner_id: int = Field(
        ..., foreign_key=f"{app_settings.APP_NAME}_user.id",
        description="客户端所有者",
    )
    owner: "User" = Relationship(back_populates="oauth_clients")

    # 授权配置
    grant_types: list[GrantTypeEnum] = Field(
        default_factory=lambda: [GrantTypeEnum.AUTHORIZATION_CODE],
        sa_column=Column(JSON, nullable=False),
        description="允许的授权类型",
    )
    scopes: list[str] = Field(
        default_factory=lambda: ["openid", "profile", "email"],
        sa_column=Column(JSON, nullable=False),
        description="允许请求的 scope",
    )
    token_endpoint_auth_method: ClientAuthMethod = Field(
        default=ClientAuthMethod.CLIENT_SECRET_BASIC,
        description="Token 端点认证方式",
    )

    # 展示信息
    homepage_url: Optional[str] = Field(
        None, max_length=500, description="应用主页",
    )
    logo_url: Optional[str] = Field(
        None, max_length=500, description="应用 Logo",
    )
    privacy_policy_url: Optional[str] = Field(
        None, max_length=500, description="隐私政策 URL",
    )

    # 状态
    is_active: bool = Field(default=True, description="是否启用")
    is_verified: bool = Field(default=False, description="是否已验证")

    # 时间戳
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    # 关联
    tokens: List["OAuthToken"] = Relationship(back_populates="client")
    consents: List["UserConsent"] = Relationship(back_populates="client")


# ---------------------------------------------------------------------------
# OAuth Scope 定义
# ---------------------------------------------------------------------------

class OAuthScope(SQLModel, table=True, table_description="OAuth Scope 权限定义"):
    """Scope 权限定义 — 支持层级 scope（如 read:user、admin:clients）"""
    __tablename__ = f"{app_settings.APP_NAME}_oauth_scope"

    id: int = Field(
        ..., sa_column=Column(Integer, autoincrement=True, primary_key=True),
    )
    name: str = Field(
        ..., max_length=100, unique=True, index=True,
        description="Scope 名称，如 openid、profile、read:user",
    )
    description: str = Field(
        ..., max_length=500, description="Scope 描述",
    )
    category: Optional[str] = Field(
        None, max_length=50, description="分类",
    )
    is_default: bool = Field(
        default=False, description="是否默认授予",
    )
    is_sensitive: bool = Field(
        default=False, description="是否需要用户明确同意",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


# ---------------------------------------------------------------------------
# 用户同意记录
# ---------------------------------------------------------------------------

class UserConsent(SQLModel, table=True, table_description="用户授权同意记录"):
    """用户对客户端 Scope 的授权同意记录"""
    __tablename__ = f"{app_settings.APP_NAME}_user_consent"

    id: int = Field(
        ..., sa_column=Column(Integer, autoincrement=True, primary_key=True),
    )
    user_id: int = Field(
        ..., foreign_key=f"{app_settings.APP_NAME}_user.id", index=True,
        description="用户 ID",
    )
    client_id: int = Field(
        ..., foreign_key=f"{app_settings.APP_NAME}_oauth_client.id", index=True,
        description="OAuth 客户端 ID",
    )
    scopes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
        description="已授权的 scope 列表",
    )
    granted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        description="授权时间",
    )
    expires_at: Optional[datetime] = Field(
        None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="授权过期时间",
    )

    # 关联
    user: "User" = Relationship(back_populates="oauth_consents")
    client: "OAuthClient" = Relationship(back_populates="consents")

    @property
    def is_expired(self) -> bool:
        """判断授权是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


# ---------------------------------------------------------------------------
# Token 记录
# ---------------------------------------------------------------------------

class OAuthToken(SQLModel, table=True, table_description="签发的 OAuth Token 记录"):
    """Token 签发记录 — 支持撤销和审计"""
    __tablename__ = f"{app_settings.APP_NAME}_oauth_token"

    id: str = Field(
        ..., max_length=64, primary_key=True,
        description="Token JTI（JWT ID）",
    )
    client_id: int = Field(
        ..., foreign_key=f"{app_settings.APP_NAME}_oauth_client.id", index=True,
    )
    user_id: Optional[int] = Field(
        None, foreign_key=f"{app_settings.APP_NAME}_user.id", index=True,
        description="用户 ID（client_credentials 时为空）",
    )
    token_type: TokenTypeEnum = Field(
        ..., description="Token 类型",
    )
    scopes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    expires_at: datetime = Field(
        ..., sa_column=Column(DateTime(timezone=True), nullable=False),
        description="过期时间",
    )
    is_revoked: bool = Field(default=False, description="是否已撤销")
    revoked_at: Optional[datetime] = Field(
        None, sa_column=Column(DateTime(timezone=True), nullable=True),
        description="撤销时间",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    # 关联
    client: "OAuthClient" = Relationship(back_populates="tokens")


# ---------------------------------------------------------------------------
# 设备指纹与信任
# ---------------------------------------------------------------------------

class DeviceFingerprint(SQLModel, table=True, table_description="设备指纹与信任评分"):
    """设备指纹存储 — 用于零信任设备评估"""
    __tablename__ = f"{app_settings.APP_NAME}_device_fingerprint"

    id: int = Field(
        ..., sa_column=Column(Integer, autoincrement=True, primary_key=True),
    )
    user_id: int = Field(
        ..., foreign_key=f"{app_settings.APP_NAME}_user.id", index=True,
        description="用户 ID",
    )
    fingerprint_hash: str = Field(
        ..., max_length=64, unique=True, index=True,
        description="设备指纹哈希",
    )
    trust_score: float = Field(
        default=0.3,
        sa_column=Column(Float, nullable=False),
        description="信任评分 (0.0-1.0)",
    )
    device_info: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=True),
        description="设备信息（浏览器、OS 等）",
    )
    is_trusted: bool = Field(default=False, description="是否为受信任设备")
    verification_count: int = Field(default=0, description="验证次数")
    first_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    last_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
