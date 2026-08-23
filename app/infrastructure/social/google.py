"""Google OAuth2 适配器（OpenID Connect userinfo）"""

from typing import Any
from urllib.parse import urlencode

import httpx

from app.infrastructure.social.base import SocialProviderAdapter, SocialUserInfo

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DEFAULT_SCOPE = "openid email profile"


class GoogleAdapter(SocialProviderAdapter):
    name = "google"

    def build_authorize_url(self, provider: Any, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": provider.scope or DEFAULT_SCOPE,
            "response_type": "code",
            "access_type": "online",
        }
        params.update(provider.additional_auth_params or {})
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_token(self, provider: Any, code: str, redirect_uri: str) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "client_id": provider.client_id,
                    "client_secret": provider.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            data = resp.json()
            if "access_token" not in data:
                raise ValueError(f"Google token exchange failed: {data}")
            return data["access_token"]

    async def fetch_userinfo(self, provider: Any, access_token: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.json()

    def normalize(self, raw: dict) -> SocialUserInfo:
        return SocialUserInfo(
            provider_uid=str(raw.get("sub") or raw.get("id") or ""),
            email=raw.get("email"),
            display_name=raw.get("name"),
            avatar_url=raw.get("picture"),
            raw=raw,
        )
