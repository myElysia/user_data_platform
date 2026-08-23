"""零信任安全模型 — 验证码、风险事件、授权码（DDD 重构新增）

- VerificationCode: ARQ 异步验证码（邮箱验证/2FA 备用/风险挑战）
- RiskEvent: 风险评估引擎事件记录
- AuthorizationCode: OAuth 授权码（由 Redis 迁移至 DB，10 分钟过期）
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import Column, Integer, String, DateTime, func, JSON, Boolean, Float
from sqlmodel import SQLModel, Field

from app.infrastructure.config.app import AppSettings

app_settings = AppSettings()


class VerificationCode(SQLModel, table=True, table_description="验证码表"):
    """验证码 — bcrypt 哈希存储，支持多用途"""
    __tablename__ = f"{app_settings.APP_NAME}_verification_code"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True))
    email: str = Field(..., max_length=255, index=True, title="目标邮箱")
    code_hash: str = Field(..., max_length=100, title="bcrypt 哈希后的验证码")
    purpose: str = Field(
        ..., max_length=50, index=True,
        title="用途: email_verify/2fa_backup/risk_challenge",
    )
    expires_at: datetime = Field(
        ..., sa_column=Column(DateTime(timezone=True), nullable=False),
        title="过期时间",
    )
    attempts: int = Field(default=0, title="校验尝试次数")
    used_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
        title="使用时间",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class RiskEvent(SQLModel, table=True, table_description="风险评估事件表"):
    """风险评估事件 — 记录每次登录风险评估的判定过程"""
    __tablename__ = f"{app_settings.APP_NAME}_risk_event"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True))
    user_id: Optional[int] = Field(
        None, foreign_key=f"{app_settings.APP_NAME}_user.id", index=True,
        title="用户 ID（登录前失败可为空）",
    )
    email: Optional[str] = Field(None, max_length=255, title="登录邮箱")
    ip: str = Field(..., max_length=64, index=True, title="来源 IP")
    device_fingerprint: Optional[str] = Field(
        None, max_length=64, index=True, title="设备指纹",
    )
    score: int = Field(..., sa_column=Column(Integer, nullable=False), title="风险评分 0-100")
    triggered_rules: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False),
        title="命中的规则列表",
    )
    action: str = Field(..., max_length=32, title="判定动作: ALLOW/CHALLENGE_2FA/BLOCK")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


class AuthorizationCode(SQLModel, table=True, table_description="OAuth 授权码表"):
    """OAuth 2.0 授权码 — DB 存储（替代 Redis），10 分钟过期"""
    __tablename__ = f"{app_settings.APP_NAME}_authorization_code"

    code: str = Field(..., primary_key=True, max_length=64, title="授权码")
    client_id: str = Field(..., max_length=64, index=True, title="客户端 ID")
    user_id: int = Field(..., foreign_key=f"{app_settings.APP_NAME}_user.id", title="用户 ID")
    scopes: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False),
        title="授权 scope 列表",
    )
    redirect_uri: str = Field(..., max_length=500, title="回调地址")
    nonce: Optional[str] = Field(None, max_length=255, title="OIDC nonce")
    code_challenge: Optional[str] = Field(None, max_length=128, title="PKCE challenge")
    code_challenge_method: Optional[str] = Field(None, max_length=16, title="PKCE method")
    expires_at: datetime = Field(
        ..., sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        title="过期时间（10 分钟）",
    )
    used_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
        title="消费时间",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
