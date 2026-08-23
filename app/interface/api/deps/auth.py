"""FastAPI 认证依赖 — Bearer Token 验证、客户端认证"""

from fastapi import Depends, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.federation.token_service import TokenManager
from app.infrastructure.database import get_db_session

security_scheme = HTTPBearer(auto_error=False)
token_manager = TokenManager()


async def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict:
    """验证 Bearer token 并返回 claims"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    try:
        claims = token_manager.verify_access_token(credentials.credentials)
        return claims
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def get_current_user_id(
    claims: dict = Depends(get_current_token),
) -> int:
    """从 token claims 提取 user_id"""
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing sub claim")
    try:
        return int(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid sub claim")


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> int | None:
    """可选认证：未携带 token 返回 None，token 无效也返回 None（供社交登录等场景）"""
    if not credentials:
        return None
    try:
        claims = token_manager.verify_access_token(credentials.credentials)
        return int(claims.get("sub", 0)) or None
    except (JWTError, ValueError):
        return None


async def get_current_client_id(
    claims: dict = Depends(get_current_token),
) -> str:
    """从 token claims 提取 client_id"""
    aud = claims.get("aud", [])
    if isinstance(aud, list):
        return aud[0] if aud else ""
    return aud


async def verify_client_auth(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> tuple[str, str]:
    """验证客户端认证（client_secret_basic 或 client_secret_post）

    返回 (client_id, client_secret)，由调用方验证。
    """
    from base64 import b64decode

    # 优先从 Authorization header (Basic)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            decoded = b64decode(auth[6:]).decode()
            client_id, client_secret = decoded.split(":", 1)
            return client_id, client_secret
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Basic auth header")

    # 其次从 body (client_secret_post)
    try:
        body = await request.json()
        client_id = body.get("client_id")
        client_secret = body.get("client_secret")
        if client_id and client_secret:
            return client_id, client_secret
    except Exception:
        pass

    raise HTTPException(status_code=401, detail="Missing client credentials")