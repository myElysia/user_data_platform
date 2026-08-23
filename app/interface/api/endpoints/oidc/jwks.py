"""OIDC JWKS 端点 — GET /.well-known/jwks.json"""

from fastapi import APIRouter

from app.domain.federation.token_service import TokenManager

router = APIRouter(tags=["OIDC JWKS"])

_token_manager = TokenManager()


@router.get("/.well-known/jwks.json")
async def jwks():
    """JWKS 端点 — 返回 RSA 公钥用于验证 JWT 签名"""
    return _token_manager.jwks()