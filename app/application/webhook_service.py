"""Webhook 服务 — 事件通知分发"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models.webhook import (
    WebhookConfig,
    WebhookDelivery,
    WebhookEventType,
    WebhookDeliveryStatus,
)
from app.infrastructure.persistence.base import BaseService

_logger = logging.getLogger("webhook")


class WebhookService(BaseService):
    """Webhook 管理服务"""

    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        super().__init__(session)
        self._client: httpx.AsyncClient | None = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def dispatch_event(
        self,
        event_type: WebhookEventType,
        payload: dict,
        client_id: Optional[int] = None,
    ):
        """分发事件到匹配的 webhook 订阅"""
        # 查询匹配的 webhook 配置
        query = select(WebhookConfig).where(
            WebhookConfig.is_active == True,
        )
        if client_id:
            query = query.where(WebhookConfig.client_id == client_id)

        result = await self.session.exec(query)
        configs = result.all()

        for config in configs:
            if event_type.value not in config.events:
                continue

            # 记录投递
            delivery = WebhookDelivery(
                config_id=config.id,
                event_type=event_type.value,
                payload=payload,
                status=WebhookDeliveryStatus.PENDING,
            )
            self.session.add(delivery)
            await self.session.commit()

            # 异步投递
            await self._deliver(config, delivery, payload)

    async def _deliver(
        self,
        config: WebhookConfig,
        delivery: WebhookDelivery,
        payload: dict,
    ):
        """执行 webhook 投递（含重试）"""
        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            delivery.attempts = attempt
            delivery.last_attempt_at = datetime.now(timezone.utc)
            delivery.status = WebhookDeliveryStatus.RETRYING

            try:
                # 生成签名
                payload_json = json.dumps(payload)
                signature = self._generate_signature(
                    config.secret, payload_json,
                )

                response = await self.http_client.post(
                    config.url,
                    content=payload_json,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Event": delivery.event_type,
                        "X-Webhook-Delivery-Id": str(delivery.id),
                        "User-Agent": "ZeroTrust-OIDC-Webhook/1.0",
                    },
                )

                delivery.response_code = response.status_code
                delivery.response_body = response.text[:1000]  # 截断长响应

                if 200 <= response.status_code < 300:
                    delivery.status = WebhookDeliveryStatus.SUCCESS
                    break
                else:
                    delivery.status = WebhookDeliveryStatus.FAILED

            except Exception as e:
                delivery.response_body = str(e)[:1000]
                delivery.status = WebhookDeliveryStatus.FAILED
                _logger.warning(
                    f"Webhook delivery failed (attempt {attempt}/{max_retries}): {e}",
                )

            self.session.add(delivery)
            await self.session.commit()

    @staticmethod
    def _generate_signature(secret: str, payload: str) -> str:
        """生成 HMAC-SHA256 签名"""
        mac = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        )
        return f"sha256={mac.hexdigest()}"

    async def verify_signature(
        self, secret: str, payload: str, signature: str,
    ) -> bool:
        """验证 webhook 签名"""
        expected = self._generate_signature(secret, payload)
        return hmac.compare_digest(expected, signature)

    async def create_config(
        self,
        client_id: int,
        url: str,
        events: list[str],
        description: str = "",
    ) -> WebhookConfig:
        """创建 webhook 配置"""
        import secrets
        config = WebhookConfig(
            client_id=client_id,
            url=url,
            secret=secrets.token_urlsafe(32),
            events=events,
            description=description,
        )
        self.session.add(config)
        await self.session.commit()
        return config

    async def get_client_configs(
        self, client_id: int,
    ) -> list[WebhookConfig]:
        result = await self.session.exec(
            select(WebhookConfig).where(WebhookConfig.client_id == client_id)
        )
        return list(result.all())

    async def get_deliveries(
        self, config_id: int, limit: int = 50,
    ) -> list[WebhookDelivery]:
        result = await self.session.exec(
            select(WebhookDelivery)
            .where(WebhookDelivery.config_id == config_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def close(self):
        if self._client:
            await self._client.aclose()
