"""联邦域 Token 服务 — 纯 JWT 签发/验证/Claims 构建（零框架依赖）

由原 app/core/oidc.py 拆分：本模块只保留与持久化、框架无关的纯逻辑。
授权流程编排（GrantHandler/OIDCProvider/DiscoveryDocument）见 application/oidc_flow.py。
"""

import base64
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Optional, Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt, JWTError

DEFAULT_ISSUER = "user_platform"

# ---------------------------------------------------------------------------
# RSA 密钥管理
# ---------------------------------------------------------------------------

@dataclass
class KeyPair:
    """RSA 密钥对（用于 JWT 签名）"""
    private_key: bytes
    public_key: bytes
    kid: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def generate(cls, kid: str | None = None, key_size: int = 2048) -> "KeyPair":
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=key_size, backend=default_backend(),
        )
        return cls(
            private_key=private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            public_key=private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
            kid=kid or str(uuid.uuid4()),
        )


# 全局密钥对（生产环境应从安全存储加载）
_KEY_PAIR = KeyPair.generate(kid="default-rsa-key")


# ---------------------------------------------------------------------------
# Token 管理器
# ---------------------------------------------------------------------------

class TokenManager:
    """JWT Token 签发、验证、刷新"""

    DEFAULT_ACCESS_TOKEN_TTL = timedelta(hours=1)
    DEFAULT_REFRESH_TOKEN_TTL = timedelta(days=30)
    DEFAULT_ID_TOKEN_TTL = timedelta(minutes=10)

    def __init__(
        self,
        key_pair: KeyPair | None = None,
        issuer: str | None = None,
    ):
        self._key_pair = key_pair or _KEY_PAIR
        self._issuer = issuer or DEFAULT_ISSUER

    # ---- 签发 ----

    def issue_access_token(
        self,
        sub: str,
        client_id: str,
        scopes: list[str],
        ttl: timedelta | None = None,
        **extra_claims,
    ) -> tuple[str, str, datetime]:
        """签发 access_token，返回 (token, jti, expires_at)"""
        jti = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        exp = now + (ttl or self.DEFAULT_ACCESS_TOKEN_TTL)
        claims = {
            "iss": self._issuer,
            "sub": sub,
            "aud": [client_id],
            "exp": exp,
            "iat": now,
            "jti": jti,
            "scope": " ".join(scopes),
            "token_type": "Bearer",
            **extra_claims,
        }
        token = jwt.encode(claims, self._key_pair.private_key, algorithm="RS256")
        return token, jti, exp

    def issue_id_token(
        self,
        sub: str,
        client_id: str,
        claims: dict[str, Any],
        ttl: timedelta | None = None,
    ) -> tuple[str, str, datetime]:
        """签发 id_token"""
        jti = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        exp = now + (ttl or self.DEFAULT_ID_TOKEN_TTL)
        id_claims = {
            "iss": self._issuer,
            "sub": sub,
            "aud": [client_id],
            "exp": exp,
            "iat": now,
            "jti": jti,
            **claims,
        }
        if "nonce" in claims:
            id_claims["nonce"] = claims["nonce"]
        token = jwt.encode(id_claims, self._key_pair.private_key, algorithm="RS256")
        return token, jti, exp

    def issue_refresh_token(self, sub: Optional[str] = None) -> tuple[str, str, datetime]:
        """签发 refresh_token（sub 携带用户 ID，供 /refresh 端点定位用户）"""
        jti = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        exp = now + self.DEFAULT_REFRESH_TOKEN_TTL
        claims = {
            "iss": self._issuer,
            "jti": jti,
            "exp": exp,
            "iat": now,
            "token_type": "refresh_token",
        }
        if sub is not None:
            claims["sub"] = sub
        token = jwt.encode(
            claims,
            self._key_pair.private_key,
            algorithm="RS256",
        )
        return token, jti, exp

    def issue_short_lived_token(
        self,
        sub: str,
        purpose: str,
        ttl: timedelta,
        **extra_claims,
    ) -> tuple[str, str, datetime]:
        """签发短期用途令牌（如 MFA 挑战令牌），返回 (token, jti, expires_at)"""
        jti = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        exp = now + ttl
        claims = {
            "iss": self._issuer,
            "sub": sub,
            "exp": exp,
            "iat": now,
            "jti": jti,
            "token_type": purpose,
            **extra_claims,
        }
        token = jwt.encode(claims, self._key_pair.private_key, algorithm="RS256")
        return token, jti, exp

    # ---- 验证 ----

    def verify(self, token: str) -> dict[str, Any]:
        """验证 JWT 并返回 claims（aud 校验由上层按场景决定，此处不校验）

        注意：python-jose 在 audience=None 且 token 携带 aud claim 时
        会抛 "Invalid audience"，因此显式关闭 aud 校验。
        """
        return jwt.decode(
            token,
            self._key_pair.public_key,
            algorithms=["RS256"],
            audience=None,
            options={"verify_aud": False},
        )

    def verify_access_token(self, token: str) -> dict[str, Any]:
        claims = self.verify(token)
        if claims.get("token_type") != "Bearer":
            raise JWTError("Invalid token type")
        return claims

    def verify_purpose_token(self, token: str, purpose: str) -> dict[str, Any]:
        """验证指定用途的短期令牌"""
        claims = self.verify(token)
        if claims.get("token_type") != purpose:
            raise JWTError(f"Invalid token type, expected {purpose}")
        return claims

    # ---- JWKS ----

    def jwks(self) -> dict:
        """生成 JWKS 文档"""
        from cryptography.hazmat.primitives.asymmetric import rsa as rsa_types
        pub_key = serialization.load_pem_public_key(
            self._key_pair.public_key, backend=default_backend(),
        )
        if not isinstance(pub_key, rsa_types.RSAPublicKey):
            raise TypeError("Expected RSA public key")
        numbers = pub_key.public_numbers()

        def _b64url(x: int) -> str:
            length = (x.bit_length() + 7) // 8
            return base64.urlsafe_b64encode(x.to_bytes(length, "big")).rstrip(b"=").decode()

        return {
            "keys": [{
                "kty": "RSA",
                "kid": self._key_pair.kid,
                "use": "sig",
                "alg": "RS256",
                "n": _b64url(numbers.n),
                "e": _b64url(numbers.e),
            }],
        }


# ---------------------------------------------------------------------------
# Claims 构建器
# ---------------------------------------------------------------------------

class ClaimsBuilder:
    """ID Token 和 UserInfo Claims 构建器"""

    @staticmethod
    def build_id_token_claims(
        user: Any,
        client_id: str,
        scopes: list[str],
        nonce: str | None = None,
    ) -> dict[str, Any]:
        claims: dict[str, Any] = {}
        if nonce:
            claims["nonce"] = nonce

        if "profile" in scopes:
            claims.update({
                "name": getattr(user, "display_name", None),
                "preferred_username": getattr(user, "email", None),
                "picture": getattr(user, "icon", None),
            })
        if "email" in scopes:
            claims.update({
                "email": getattr(user, "email", None),
                "email_verified": getattr(user, "email_verified", False),
            })
        if "phone" in scopes:
            claims.update({
                "phone_number": getattr(user, "phone", None),
                "phone_number_verified": getattr(user, "phone_verified", False),
            })
        return claims

    @staticmethod
    def build_userinfo_claims(user: Any, scopes: list[str]) -> dict[str, Any]:
        claims: dict[str, Any] = {"sub": str(user.id)}
        if "profile" in scopes:
            claims.update({
                "name": getattr(user, "display_name", None),
                "preferred_username": getattr(user, "email", None),
                "picture": getattr(user, "icon", None),
                "locale": getattr(user, "language", None),
            })
        if "email" in scopes:
            claims.update({
                "email": getattr(user, "email", None),
                "email_verified": getattr(user, "email_verified", False),
            })
        if "phone" in scopes:
            claims.update({
                "phone_number": getattr(user, "phone", None),
                "phone_number_verified": getattr(user, "phone_verified", False),
            })
        return claims


# ---------------------------------------------------------------------------
# PKCE 校验（纯函数）
# ---------------------------------------------------------------------------

def verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    """校验 PKCE code_verifier 与 code_challenge 是否匹配（RFC 7636）"""
    if method == "S256":
        digest = sha256(code_verifier.encode()).digest()
        actual = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    else:
        actual = code_verifier
    return actual == code_challenge


__all__ = [
    "KeyPair",
    "TokenManager",
    "ClaimsBuilder",
    "verify_pkce",
    "DEFAULT_ISSUER",
]
