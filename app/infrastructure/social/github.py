"""GitHub OAuth2 适配器"""

from typing import Any
from urllib.parse import urlencode

import httpx

from app.infrastructure.social.base import SocialProviderAdapter, SocialUserInfo

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USERINFO_URL = "https://api.github.com/user"
EMAILS_URL = "https://api.github.com/user/emails"
DEFAULT_SCOPE = "read:user user:email"


class GitHubAdapter(SocialProviderAdapter):
    name = "github"

    def build_authorize_url(self, provider: Any, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": provider.scope or DEFAULT_SCOPE,
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
                },
                headers={"Accept": "application/json"},
            )
            data = resp.json()
            if "access_token" not in data:
                raise ValueError(f"GitHub token exchange failed: {data}")
            return data["access_token"]

    async def fetch_userinfo(self, provider: Any, access_token: str) -> dict:
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(USERINFO_URL, headers=headers)
            data = resp.json()
            # GitHub userinfo 不返回 email，需单独拉取（取 primary）
            if not data.get("email"):
                try:
                    emails_resp = await client.get(EMAILS_URL, headers=headers)
                    for entry in emails_resp.json():
                        if entry.get("primary") and entry.get("email"):
                            data["email"] = entry["email"]
                            break
                except Exception:
                    pass
            return data

    def normalize(self, raw: dict) -> SocialUserInfo:
        return SocialUserInfo(
            provider_uid=str(raw.get("id") or raw.get("node_id") or ""),
            email=raw.get("email"),
            display_name=raw.get("name") or raw.get("login"),
            avatar_url=raw.get("avatar_url"),
            raw=raw,
        )
