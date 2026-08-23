"""OIDC 授权流程编排 — GrantHandler/OIDCProvider/DiscoveryDocument

由原 app/core/oidc.py 拆分：
- 领域纯 JWT 逻辑（KeyPair/TokenManager/ClaimsBuilder/PKCE）→ domain/federation/token_service.py
- 本模块负责数据库交互与用例编排（授权码 DB 化、Token 记录、客户端认证）
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.federation.token_service import ClaimsBuilder, TokenManager, verify_pkce
from app.infrastructure.persistence.models import User
from app.infrastructure.persistence.models.oauth import (
    OAuthClient,
    OAuthToken,
    TokenTypeEnum,
)
from app.infrastructure.persistence.models.security import AuthorizationCode

AUTH_CODE_TTL = timedelta(minutes=10)
AUTH_REQUEST_KEY_PREFIX = "pending:"


# ---------------------------------------------------------------------------
# OIDC Discovery 文档（RFC 8414）
# ---------------------------------------------------------------------------

class DiscoveryDocument:
    """OIDC Discovery 文档生成"""

    @staticmethod
    def generate(base_url: str) -> dict:
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/authorize",
            "token_endpoint": f"{base_url}/token",
            "userinfo_endpoint": f"{base_url}/userinfo",
            "jwks_uri": f"{base_url}/.well-known/jwks.json",
            "registration_endpoint": f"{base_url}/register",
            "scopes_supported": ["openid", "profile", "email", "phone"],
            "response_types_supported": ["code"],
            "grant_types_supported": [
                "authorization_code", "client_credentials", "refresh_token",
            ],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic", "client_secret_post",
            ],
            "claims_supported": [
                "sub", "iss", "aud", "exp", "iat",
                "name", "preferred_username", "email", "email_verified",
            ],
            "code_challenge_methods_supported": ["S256", "plain"],
        }


# ---------------------------------------------------------------------------
# 授权类型处理器
# ---------------------------------------------------------------------------

class GrantHandler:
    """OAuth 2.0 授权类型处理器"""

    def __init__(self, session: AsyncSession, tokens: TokenManager):
        self.session = session
        self.tokens = tokens

    async def handle_authorization_code(
        self,
        code: str,
        client: OAuthClient,
        redirect_uri: str = "",
        code_verifier: str | None = None,
    ) -> dict:
        """authorization_code 授权 — 从 DB 消费授权码（10 分钟过期、一次性）"""
        auth_code = await self.session.get(AuthorizationCode, code)
        if not auth_code:
            raise ValueError("invalid_grant: Unknown authorization code")
        if auth_code.is_used:
            raise ValueError("invalid_grant: Authorization code already used")
        if auth_code.is_expired:
            raise ValueError("invalid_grant: Authorization code expired")
        if auth_code.client_id != client.client_id:
            raise ValueError("invalid_grant: Code was issued to another client")
        if redirect_uri and redirect_uri != auth_code.redirect_uri:
            raise ValueError("invalid_grant: redirect_uri mismatch")

        # PKCE 校验（RFC 7636）
        if auth_code.code_challenge:
            if not code_verifier:
                raise ValueError("invalid_grant: Missing code_verifier (PKCE)")
            if not verify_pkce(
                code_verifier,
                auth_code.code_challenge,
                auth_code.code_challenge_method or "S256",
            ):
                raise ValueError("invalid_grant: PKCE verification failed")

        # 标记已消费
        auth_code.used_at = datetime.now(timezone.utc)
        self.session.add(auth_code)

        scopes = list(auth_code.scopes)
        user = await self.session.get(User, auth_code.user_id)
        if not user:
            raise ValueError("invalid_grant: User not found")

        return await self._issue_user_tokens(user, client, scopes, nonce=auth_code.nonce)

    async def handle_client_credentials(
        self, client: OAuthClient, scopes: list[str],
    ) -> dict:
        """client_credentials 授权 — 机器对机器"""
        allowed = [s for s in scopes if s in client.scopes]
        access_token, jti, exp = self.tokens.issue_access_token(
            sub=client.client_id,
            client_id=client.client_id,
            scopes=allowed,
        )
        self.session.add(OAuthToken(
            id=jti,
            client_id=client.id,
            user_id=None,
            token_type=TokenTypeEnum.ACCESS_TOKEN,
            scopes=allowed,
            expires_at=exp,
        ))
        await self.session.commit()
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self._expires_in(exp),
            "scope": " ".join(allowed),
        }

    async def handle_refresh_token(
        self, refresh_token: str, client: OAuthClient,
    ) -> dict:
        """refresh_token 授权 — 校验 refresh token 记录后签发新 access token"""
        claims = self.tokens.verify(refresh_token)
        if claims.get("token_type") != "refresh_token":
            raise ValueError("invalid_grant: Not a refresh token")
        jti = claims.get("jti")
        record = await self.session.get(OAuthToken, jti)
        if not record or record.is_revoked:
            raise ValueError("invalid_grant: Refresh token revoked")

        scopes = list(record.scopes)
        user_id = record.user_id
        sub = str(user_id) if user_id else client.client_id

        access_token, new_jti, exp = self.tokens.issue_access_token(
            sub=sub,
            client_id=client.client_id,
            scopes=scopes,
        )
        self.session.add(OAuthToken(
            id=new_jti,
            client_id=client.id,
            user_id=user_id,
            token_type=TokenTypeEnum.ACCESS_TOKEN,
            scopes=scopes,
            expires_at=exp,
        ))
        await self.session.commit()
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self._expires_in(exp),
            "scope": " ".join(scopes),
        }

    async def _issue_user_tokens(
        self,
        user,
        client: OAuthClient,
        scopes: list[str],
        nonce: str | None = None,
    ) -> dict:
        """为用户签发 access_token + refresh_token + id_token，并记录 OAuthToken"""
        access_token, access_jti, access_exp = self.tokens.issue_access_token(
            sub=str(user.id),
            client_id=client.client_id,
            scopes=scopes,
        )
        refresh_token, refresh_jti, refresh_exp = self.tokens.issue_refresh_token()
        id_claims = ClaimsBuilder.build_id_token_claims(
            user, client.client_id, scopes, nonce=nonce,
        )
        id_token, id_jti, id_exp = self.tokens.issue_id_token(
            sub=str(user.id),
            client_id=client.client_id,
            claims=id_claims,
        )

        self.session.add(OAuthToken(
            id=access_jti, client_id=client.id, user_id=user.id,
            token_type=TokenTypeEnum.ACCESS_TOKEN, scopes=scopes, expires_at=access_exp,
        ))
        self.session.add(OAuthToken(
            id=refresh_jti, client_id=client.id, user_id=user.id,
            token_type=TokenTypeEnum.REFRESH_TOKEN, scopes=scopes, expires_at=refresh_exp,
        ))
        self.session.add(OAuthToken(
            id=id_jti, client_id=client.id, user_id=user.id,
            token_type=TokenTypeEnum.ID_TOKEN, scopes=scopes, expires_at=id_exp,
        ))
        await self.session.commit()

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self._expires_in(access_exp),
            "refresh_token": refresh_token,
            "id_token": id_token,
            "scope": " ".join(scopes),
        }

    @staticmethod
    def _expires_in(exp: datetime) -> int:
        return max(0, int((exp - datetime.now(timezone.utc)).total_seconds()))


# ---------------------------------------------------------------------------
# OIDC 提供者门面
# ---------------------------------------------------------------------------

class OIDCProvider:
    """OIDC 提供者门面 — 客户端认证、授权码签发、授权请求上下文、Token 撤销"""

    def __init__(self, session: AsyncSession, base_url: str = ""):
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.tokens = TokenManager()
        self.grants = GrantHandler(session, self.tokens)

    # ---- 客户端认证 ----

    async def get_client(self, client_id: str) -> OAuthClient | None:
        result = await self.session.exec(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True,  # noqa: E712
            )
        )
        return result.first()

    async def authenticate_client(
        self, client_id: str, client_secret: str,
    ) -> OAuthClient:
        client = await self.get_client(client_id)
        if not client:
            raise ValueError("invalid_client: Unknown client")
        if client.client_secret != client_secret:
            raise ValueError("invalid_client: Invalid client secret")
        return client

    # ---- 授权码签发（DB 存储，替代 Redis） ----

    async def issue_authorization_code(
        self,
        client: OAuthClient,
        user_id: int,
        redirect_uri: str,
        scopes: list[str],
        nonce: str = "",
        code_challenge: str = "",
        code_challenge_method: str = "S256",
    ) -> AuthorizationCode:
        """签发授权码并持久化（10 分钟过期）"""
        code = secrets.token_urlsafe(32)
        auth_code = AuthorizationCode(
            code=code,
            client_id=client.client_id,
            user_id=user_id,
            scopes=scopes,
            redirect_uri=redirect_uri,
            nonce=nonce or None,
            code_challenge=code_challenge or None,
            code_challenge_method=code_challenge_method or None,
            expires_at=datetime.now(timezone.utc) + AUTH_CODE_TTL,
        )
        self.session.add(auth_code)
        await self.session.commit()
        return auth_code

    # ---- 授权请求上下文（同意流程，DB 存储，替代 Redis） ----

    async def store_auth_request(
        self,
        client: OAuthClient,
        user_id: int,
        redirect_uri: str,
        scopes: list[str],
        state: str = "",
        nonce: str = "",
        code_challenge: str = "",
        code_challenge_method: str = "S256",
    ) -> str:
        """存储授权请求上下文（用于同意页回调），返回 pending key"""
        key = f"{AUTH_REQUEST_KEY_PREFIX}{state or secrets.token_hex(16)}"
        record = AuthorizationCode(
            code=key,
            client_id=client.client_id,
            user_id=user_id,
            scopes=scopes,
            redirect_uri=redirect_uri,
            nonce=nonce or None,
            code_challenge=code_challenge or None,
            code_challenge_method=code_challenge_method or None,
            expires_at=datetime.now(timezone.utc) + AUTH_CODE_TTL,
        )
        self.session.add(record)
        await self.session.commit()
        return key

    async def consume_auth_request(self, key: str) -> AuthorizationCode | None:
        """消费授权请求上下文（用户同意后），一次性"""
        record = await self.session.get(AuthorizationCode, key)
        if not record or record.is_expired or record.is_used:
            return None
        record.used_at = datetime.now(timezone.utc)
        self.session.add(record)
        await self.session.commit()
        return record

    # ---- Token 撤销（RFC 7009） ----

    async def revoke_token(self, jti: str) -> bool:
        token = await self.session.get(OAuthToken, jti)
        if not token or token.is_revoked:
            return False
        token.is_revoked = True
        token.revoked_at = datetime.now(timezone.utc)
        self.session.add(token)
        await self.session.commit()
        return True
