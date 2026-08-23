"""通用 OAuth2 适配器 — 覆盖微信/Gitee 等未内置平台

平台端点（authorization_url/token_url/userinfo_url）全部来自 OauthProvider
配置，适配器不做平台特判；字段提取在 normalize 中按常见约定兜底，
平台差异字段由 admin 配置的 FieldMapping（transform_fields）先行处理。
"""

from typing import Any
from urllib.parse import urlencode

import httpx

from app.infrastructure.social.base import SocialProviderAdapter, SocialUserInfo

UID_CANDIDATE_KEYS = ("id", "sub", "uid", "openid", "unionid", "user_id")


class GenericAdapter(SocialProviderAdapter):
    def __init__(self, name: str):
        self.name = name

    def build_authorize_url(self, provider: Any, state: str, redirect_uri: str) -> str:
        if not provider.authorization_url:
            raise ValueError(f"Provider {self.name} has no authorization_url configured")
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
        }
        if provider.scope:
            params["scope"] = provider.scope
        params.update(provider.additional_auth_params or {})
        return f"{provider.authorization_url}?{urlencode(params)}"

    async def exchange_token(self, provider: Any, code: str, redirect_uri: str) -> str:
        if not provider.token_url:
            raise ValueError(f"Provider {self.name} has no token_url configured")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                provider.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": provider.client_id,
                    "client_secret": provider.client_secret,
                    "redirect_uri": redirect_uri,
                },
            )
            data = resp.json()
            if "access_token" not in data:
                raise ValueError(
                    f"{self.name} token exchange failed: {str(data)[:200]}",
                )
            return data["access_token"]

    async def fetch_userinfo(self, provider: Any, access_token: str) -> dict:
        if not provider.userinfo_url:
            raise ValueError(f"Provider {self.name} has no userinfo_url configured")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                provider.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.json()

    def normalize(self, raw: dict) -> SocialUserInfo:
        uid = next((raw.get(k) for k in UID_CANDIDATE_KEYS if raw.get(k)), "")
        return SocialUserInfo(
            provider_uid=str(uid),
            email=raw.get("email"),
            display_name=(
                raw.get("name")
                or raw.get("nickname")
                or raw.get("display_name")
                or raw.get("login")
            ),
            avatar_url=(
                raw.get("avatar_url")
                or raw.get("picture")
                or raw.get("headimgurl")
                or raw.get("avatar")
            ),
            raw=raw,
        )
