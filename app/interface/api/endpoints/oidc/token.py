"""OIDC Token 端点 — POST /token, POST /token/revoke"""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.oidc_flow import OIDCProvider
from app.infrastructure.database import get_db_session
from app.interface.api.schemas.oidc import (
    TokenRequest,
    TokenResponse,
    TokenErrorResponse,
    RevokeRequest,
)

router = APIRouter(tags=["OIDC Token"])


@router.post("/token")
async def token(
    request: Request,
    body: TokenRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """OAuth 2.0 / OIDC Token Endpoint

    支持的 grant_type:
    - authorization_code
    - client_credentials
    - refresh_token
    """
    provider = OIDCProvider(
        session,
        base_url=str(request.base_url).rstrip("/"),
    )

    try:
        # 1. 验证客户端
        client_id = body.client_id or ""
        client_secret = body.client_secret or ""

        # 尝试从 Authorization header 解析
        auth = request.headers.get("Authorization", "")
        from base64 import b64decode
        if auth.startswith("Basic "):
            try:
                decoded = b64decode(auth[6:]).decode()
                client_id, client_secret = decoded.split(":", 1)
            except Exception:
                pass

        client = await provider.authenticate_client(client_id, client_secret)

        # 2. 处理不同授权类型
        if body.grant_type == "authorization_code":
            if not body.code:
                raise HTTPException(status_code=400, detail="Missing authorization code")
            result = await provider.grants.handle_authorization_code(
                code=body.code,
                client=client,
                redirect_uri=body.redirect_uri or "",
                code_verifier=body.code_verifier,
            )
        elif body.grant_type == "client_credentials":
            scopes = [s.strip() for s in (body.scope or "openid").split() if s.strip()]
            result = await provider.grants.handle_client_credentials(client, scopes)
        elif body.grant_type == "refresh_token":
            if not body.refresh_token:
                raise HTTPException(status_code=400, detail="Missing refresh_token")
            result = await provider.grants.handle_refresh_token(
                body.refresh_token, client,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"unsupported_grant_type: {body.grant_type}",
            )

        return TokenResponse(**result)

    except ValueError as e:
        error_msg = str(e)
        if ":" in error_msg:
            error, description = error_msg.split(":", 1)
        else:
            error, description = "invalid_request", error_msg
        return TokenErrorResponse(error=error.strip(), error_description=description.strip())
    except HTTPException:
        raise
    except Exception as e:
        return TokenErrorResponse(error="server_error", error_description=str(e))


@router.post("/token/revoke")
async def revoke_token(
    request: Request,
    body: RevokeRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Token 撤销端点 — RFC 7009"""
    provider = OIDCProvider(session)

    try:
        # 验证 token 获取 jti
        claims = provider.tokens.verify(body.token)
        jti = claims.get("jti")
        if jti:
            await provider.revoke_token(jti)
    except Exception:
        # RFC 7009: 即使 token 无效也返回 200
        pass

    return {"message": "Token revoked"}