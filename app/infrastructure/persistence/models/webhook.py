"""Webhook 模型 — 客户端事件通知系统"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, func, Boolean, JSON, Text
from sqlmodel import SQLModel, Field

from app.infrastructure.config.app import AppSettings

app_settings = AppSettings()


class WebhookEventType(str, Enum):
    """Webhook 事件类型"""
    CLIENT_CREATED = "client.created"
    CLIENT_UPDATED = "client.updated"
    CLIENT_DELETED = "client.deleted"
    CLIENT_SECRET_ROTATED = "client.secret_rotated"
    TOKEN_ISSUED = "token.issued"
    TOKEN_REVOKED = "token.revoked"
    USER_CONSENT_GRANTED = "user.consent_granted"
    USER_CONSENT_REVOKED = "user.consent_revoked"
    RISK_DETECTED = "security.risk_detected"


class WebhookDeliveryStatus(str, Enum):
    """Webhook 投递状态"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookConfig(SQLModel, table=True, table_description="Webhook 配置"):
    """客户端 Webhook 配置"""
    __tablename__ = f"{app_settings.APP_NAME}_webhook_config"

    id: int = Field(
        ..., sa_column=Column(Integer, autoincrement=True, primary_key=True),
    )
    client_id: int = Field(
        ..., foreign_key=f"{app_settings.APP_NAME}_oauth_client.id",
        description="关联的 OAuth 客户端",
    )
    url: str = Field(..., max_length=500, description="Webhook 回调 URL")
    secret: str = Field(
        ..., max_length=100, description="Webhook 签名密钥",
    )
    events: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
        description="订阅的事件类型列表",
    )
    is_active: bool = Field(default=True, description="是否启用")
    description: Optional[str] = Field(
        None, sa_column=Column(Text, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class WebhookDelivery(SQLModel, table=True, table_description="Webhook 投递记录"):
    """Webhook 投递日志 — 用于审计和重试"""
    __tablename__ = f"{app_settings.APP_NAME}_webhook_delivery"

    id: int = Field(
        ..., sa_column=Column(Integer, autoincrement=True, primary_key=True),
    )
    config_id: int = Field(
        ..., foreign_key=f"{app_settings.APP_NAME}_webhook_config.id", index=True,
    )
    event_type: str = Field(..., max_length=100, description="事件类型")
    payload: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="发送的 payload",
    )
    status: WebhookDeliveryStatus = Field(
        default=WebhookDeliveryStatus.PENDING,
    )
    response_code: Optional[int] = Field(None, description="HTTP 响应码")
    response_body: Optional[str] = Field(
        None, sa_column=Column(Text, nullable=True),
        description="响应内容",
    )
    attempts: int = Field(default=1, description="投递尝试次数")
    last_attempt_at: Optional[datetime] = Field(
        None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
