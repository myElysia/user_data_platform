"""社交登录端点 — 授权跳转/回调/绑定管理

路由前缀 /api/v1/auth/social：
- GET    /{provider}/authorize?bind=1  生成 state 并 302 跳转第三方平台
- GET    /{provider}/callback         平台回调（换 token/拉 userinfo/绑定或登录）
- GET    /accounts                    我的绑定列表
- DELETE /{account_id}                解绑
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.social_use_cases import social_use_cases
from app.infrastructure.database import get_db_session
from app.interface.api.deps.auth import get_current_user_id, get_optional_user_id
from app.interface.api.schemas.social import SocialAccountResponse

router = APIRouter(prefix="/v1/auth/social", tags=["Social"])


@router.get("/{provider}/authorize")
async def social_authorize(
    provider: str,
    request: Request,
    bind: int = 0,
    redirect_uri: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    current_user_id: Optional[int] = Depends(get_optional_user_id),
):
    """跳转第三方平台授权页 — bind=1 表示绑定流程（需已登录）

    redirect_uri 可选：前端 SSR 页面模式的自定义回调地址
    （如 http://localhost:3000/social/github/callback），
    未传时默认后端 /api/v1/auth/social/{provider}/callback。
    """
    authorize_url = await social_use_cases.authorize(
        session, provider, bool(bind), request, redirect_uri,
    )
    return RedirectResponse(authorize_url, status_code=302)


@router.get("/{provider}/callback")
async def social_callback(
    provider: str,
    code: str,
    state: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user_id: Optional[int] = Depends(get_optional_user_id),
):
    """平台回调 — 绑定（已登录）或登录/注册（未登录）"""
    return await social_use_cases.callback(
        session, provider, code, state, request, current_user_id,
    )


@router.get("/accounts", response_model=list[SocialAccountResponse])
async def social_accounts(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """我的社交账号绑定列表"""
    accounts = await social_use_cases.list_accounts(session, user_id)
    return [SocialAccountResponse(**a) for a in accounts]


@router.delete("/{account_id}")
async def social_unbind(
    account_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """解绑社交账号"""
    await social_use_cases.unbind(session, user_id, account_id, request)
    return {"message": "Social account unbound"}
