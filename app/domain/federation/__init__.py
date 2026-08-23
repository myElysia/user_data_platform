"""联邦域 — OAuth/OIDC/社交登录（纯 Python，零框架依赖）"""

from app.domain.federation.token_service import (
    KeyPair,
    TokenManager,
    ClaimsBuilder,
    verify_pkce,
    DEFAULT_ISSUER,
)

__all__ = ["KeyPair", "TokenManager", "ClaimsBuilder", "verify_pkce", "DEFAULT_ISSUER"]
