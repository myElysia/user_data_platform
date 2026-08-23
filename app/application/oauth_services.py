"""OAuth 服务层 — 客户端管理、Token 管理"""

import secrets
from datetime import datetime, timezone

from fastapi import Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models.oauth import (
    OAuthClient,
    OAuthToken,
    UserConsent,
    GrantTypeEnum,
    TokenTypeEnum,
)
from app.infrastructure.persistence.base import BaseService


class OAuthClientService(BaseService):
    """OAuth 客户端管理服务"""

    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        super().__init__(session)

    async def get_by_client_id(self, client_id: str) -> OAuthClient | None:
        result = await self.session.exec(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True,
            )
        )
        return result.first()

    async def get_user_clients(self, user_id: int) -> list[OAuthClient]:
        result = await self.session.exec(
            select(OAuthClient).where(OAuthClient.owner_id == user_id)
        )
        return list(result.all())

    async def create_client(
        self,
        name: str,
        owner_id: int,
        callback_urls: list[str],
        scopes: list[str] | None = None,
        grant_types: list[str] | None = None,
        description: str = "",
        homepage_url: str = "",
        logo_url: str = "",
    ) -> OAuthClient:
        """创建新的 OAuth 客户端"""
        client = OAuthClient(
            client_id=f"oidc_{secrets.token_hex(16)}",
            client_secret=secrets.token_urlsafe(48),
            name=name,
            description=description,
            callback_urls=callback_urls,
            owner_id=owner_id,
            grant_types=[
                GrantTypeEnum(g) for g in (grant_types or ["authorization_code"])
            ],
            scopes=scopes or ["openid", "profile", "email"],
            homepage_url=homepage_url,
            logo_url=logo_url,
        )
        self.session.add(client)
        await self.session.commit()
        return client

    async def rotate_secret(self, client_id: str, user_id: int) -> str:
        """轮换客户端密钥，返回新密钥"""
        result = await self.session.exec(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.owner_id == user_id,
            )
        )
        client = result.first()
        if not client:
            raise ValueError("Client not found")

        client.client_secret = secrets.token_urlsafe(48)
        client.updated_at = datetime.now(timezone.utc)
        self.session.add(client)
        await self.session.commit()
        return client.client_secret


class TokenService(BaseService):
    """Token 管理服务"""

    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        super().__init__(session)

    async def get_token(self, jti: str) -> OAuthToken | None:
        return await self.session.get(OAuthToken, jti)

    async def revoke_token(self, jti: str) -> bool:
        token = await self.session.get(OAuthToken, jti)
        if not token or token.is_revoked:
            return False
        token.is_revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        self.session.add(token)
        await self.session.commit()
        return True

    async def get_user_tokens(
        self, user_id: int, include_revoked: bool = False,
    ) -> list[OAuthToken]:
        query = select(OAuthToken).where(OAuthToken.user_id == user_id)
        if not include_revoked:
            query = query.where(OAuthToken.is_revoked == False)
        result = await self.session.exec(query)
        return list(result.all())

    async def revoke_all_user_tokens(self, user_id: int) -> int:
        """撤销用户所有 token，返回撤销数量"""
        tokens = await self.get_user_tokens(user_id)
        count = 0
        for token in tokens:
            token.is_revoked = True
            token.revoked_at = datetime.now(timezone.utc)
            self.session.add(token)
            count += 1
        await self.session.commit()
        return count


class ConsentService(BaseService):
    """用户同意管理服务"""

    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        super().__init__(session)

    async def get_consent(
        self, user_id: int, client_id: int,
    ) -> UserConsent | None:
        result = await self.session.exec(
            select(UserConsent).where(
                UserConsent.user_id == user_id,
                UserConsent.client_id == client_id,
            )
        )
        return result.first()

    async def revoke_all_consents(self, user_id: int) -> int:
        """撤销用户所有同意，返回撤销数量"""
        result = await self.session.exec(
            select(UserConsent).where(UserConsent.user_id == user_id)
        )
        consents = result.all()
        for c in consents:
            await self.session.delete(c)
        await self.session.commit()
        return len(consents)


class ConsentManager(BaseService):
    """用户授权同意管理器（原 domain/federation/consent.py 的 DB 操作部分）

    纯判定逻辑见 app.domain.federation.consent.decide_consent_needed。
    """

    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        super().__init__(session)

    async def get_consent(
        self, user_id: int, client_id: int,
    ) -> UserConsent | None:
        result = await self.session.exec(
            select(UserConsent).where(
                UserConsent.user_id == user_id,
                UserConsent.client_id == client_id,
            )
        )
        return result.first()

    async def grant_consent(
        self,
        user_id: int,
        client_id: int,
        scopes: list[str],
        expires_at: datetime | None = None,
    ) -> UserConsent:
        """授予同意"""
        consent = await self.get_consent(user_id, client_id)
        if consent:
            consent.scopes = scopes
            consent.granted_at = datetime.now(timezone.utc)
            consent.expires_at = expires_at
        else:
            consent = UserConsent(
                user_id=user_id,
                client_id=client_id,
                scopes=scopes,
                expires_at=expires_at,
            )
            self.session.add(consent)
        await self.session.commit()
        return consent

    async def revoke_consent(
        self, user_id: int, client_id: int,
    ) -> bool:
        """撤销同意"""
        consent = await self.get_consent(user_id, client_id)
        if not consent:
            return False
        consent.scopes = []
        await self.session.commit()
        return True

    async def needs_consent(
        self,
        user_id: int,
        client,
        requested_scopes: list[str],
    ) -> bool:
        """判断是否需要用户同意（委托领域纯逻辑）"""
        from app.domain.federation.consent import decide_consent_needed

        consent = await self.get_consent(user_id, client.id)
        return decide_consent_needed(
            consent.scopes if consent else None,
            consent.is_expired if consent else True,
            requested_scopes,
        )

    async def get_consent_page_data(
        self, user_id: int, client, requested_scopes: list[str],
    ) -> dict:
        """获取同意页面所需数据"""
        from app.infrastructure.persistence.models.oauth import OAuthScope

        scope_descriptions = {}
        result = await self.session.exec(
            select(OAuthScope).where(OAuthScope.name.in_(requested_scopes))
        )
        for scope in result.all():
            scope_descriptions[scope.name] = scope.description

        return {
            "client_name": client.name,
            "client_description": client.description,
            "client_logo": client.logo_url,
            "client_homepage": client.homepage_url,
            "scopes": [
                {
                    "name": s,
                    "description": scope_descriptions.get(s, s),
                }
                for s in requested_scopes
            ],
        }
