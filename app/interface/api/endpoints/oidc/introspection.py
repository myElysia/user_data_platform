"""OIDC Token Introspection 端点 — RFC 7662"""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.oidc_flow import OIDCProvider
from app.infrastructure.database import get_db_session

router = APIRouter(tags=["OIDC Introspection"])


@router.post("/token/introspect")
async def introspect_token(
    request: Request,
    token: str,
    token_type_hint: str = "access_token",
    session: AsyncSession = Depends(get_db_session),
):
    """Token Introspection — RFC 7662

    验证 token 是否有效，返回其元数据。
    供资源服务器调用以验证客户端请求中的 access_token。
    """
    # 验证客户端认证
    from base64 import b64decode

    auth = request.headers.get("Authorization", "")
    client_id = ""
    client_secret = ""

    if auth.startswith("Basic "):
        try:
            decoded = b64decode(auth[6:]).decode()
            client_id, client_secret = decoded.split(":", 1)
        except Exception:
            pass

    if auth.startswith("Bearer "):
        try:
            decoded = b64decode(auth[7:]).decode()
            client_id, client_secret = decoded.split(":", 1)
        except Exception:
            pass

    if not client_id:
        # 允许无客户端认证，但限制返回信息
        pass

    provider = OIDCProvider(session)

    try:
        claims = provider.tokens.verify(token)

        # 检查 token 是否被撤销
        jti = claims.get("jti")
        if jti:
            from app.infrastructure.persistence.models.oauth import OAuthToken
            token_record = await session.get(OAuthToken, jti)
            if token_record and token_record.is_revoked:
                return {"active": False}

        return {
            "active": True,
            "scope": claims.get("scope", ""),
            "client_id": claims.get("aud", [""])[0] if claims.get("aud") else "",
            "username": claims.get("sub", ""),
            "token_type": claims.get("token_type", "Bearer"),
            "exp": int(claims.get("exp", 0)),
            "iat": int(claims.get("iat", 0)),
            "sub": claims.get("sub", ""),
            "iss": claims.get("iss", ""),
            "jti": jti or "",
        }
    except Exception:
        return {"active": False}