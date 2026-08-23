"""OIDC Authorization 端点 — GET /authorize"""

from urllib.parse import urlencode

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.oidc_flow import OIDCProvider
from app.application.oauth_services import ConsentManager
from app.domain.federation.token_service import TokenManager
from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models.oauth import OAuthClient

router = APIRouter(tags=["OIDC Authorization"])


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    scope: str = "openid",
    state: str = "",
    nonce: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
    prompt: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """OAuth 2.0 / OIDC Authorization Endpoint"""
    provider = OIDCProvider(session, base_url=str(request.base_url).rstrip("/"))

    # 1. 验证客户端
    client = await provider.get_client(client_id)
    if not client:
        raise HTTPException(status_code=400, detail="invalid_client: Unknown client")

    # 2. 验证 redirect_uri
    if redirect_uri not in client.callback_urls:
        raise HTTPException(status_code=400, detail="invalid_redirect_uri")

    # 3. 解析 scope
    requested_scopes = [s.strip() for s in scope.split() if s.strip()]
    allowed_scopes = [s for s in requested_scopes if s in client.scopes]
    if not allowed_scopes:
        raise HTTPException(status_code=400, detail="invalid_scope")

    # 4. 检查用户登录状态（简化：从 cookie/token 获取 user_id）
    # 实际生产环境需要完整的 session 管理
    user_id = _get_user_from_request(request)
    if not user_id:
        # 未登录 — 重定向到登录页
        login_url = f"/login?{urlencode({'redirect_uri': str(request.url)})}"
        return RedirectResponse(login_url)

    # 5. 检查是否需要用户同意
    consent_manager = ConsentManager(session)
    needs_consent = await consent_manager.needs_consent(
        user_id, client, allowed_scopes,
    )

    if needs_consent and prompt != "none":
        # 需要同意 — 重定向到同意页面
        consent_data = await consent_manager.get_consent_page_data(
            user_id, client, allowed_scopes,
        )
        # 存储授权请求上下文到 DB（用于同意后回调，10 分钟过期）
        auth_request_key = await provider.store_auth_request(
            client, user_id, redirect_uri, allowed_scopes,
            state=state, nonce=nonce,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
        consent_url = f"/consent?key={auth_request_key.split(':')[-1]}"
        return RedirectResponse(consent_url)

    # 6. 生成授权码并重定向
    return await _issue_authorization_code(
        provider, client, user_id, redirect_uri,
        allowed_scopes, state, nonce, code_challenge, code_challenge_method,
    )


async def _issue_authorization_code(
    provider: OIDCProvider,
    client: OAuthClient,
    user_id: int,
    redirect_uri: str,
    scopes: list[str],
    state: str = "",
    nonce: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
):
    """生成授权码（DB 存储，10 分钟有效）并返回重定向响应"""
    auth_code = await provider.issue_authorization_code(
        client, user_id, redirect_uri, scopes,
        nonce=nonce,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )

    # 构建重定向 URL
    params = {"code": auth_code.code}
    if state:
        params["state"] = state

    redirect_url = f"{redirect_uri}?{urlencode(params)}"
    return RedirectResponse(redirect_url)


def _get_user_from_request(request: Request) -> int | None:
    """从请求中提取用户 ID（简化实现）"""
    # 从 Authorization header 提取
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            token_manager = TokenManager()
            claims = token_manager.verify_access_token(auth[7:])
            sub = claims.get("sub")
            if sub:
                return int(sub)
        except Exception:
            pass
    # 从 session cookie 提取（简化）
    session_cookie = request.cookies.get("session_token")
    if session_cookie:
        try:
            token_manager = TokenManager()
            claims = token_manager.verify(session_cookie)
            sub = claims.get("sub")
            if sub:
                return int(sub)
        except Exception:
            pass
    return None
