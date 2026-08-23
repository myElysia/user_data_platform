"""OIDC Discovery 端点 — GET /.well-known/openid-configuration"""

from fastapi import APIRouter, Request

from app.application.oidc_flow import DiscoveryDocument

router = APIRouter(tags=["OIDC Discovery"])


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request):
    """OIDC Discovery 文档 — RFC 8414"""
    base_url = str(request.base_url).rstrip("/")
    return DiscoveryDocument.generate(base_url)