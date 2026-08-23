"""社交登录适配器抽象 — 第三方 OAuth2 平台接入协议"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SocialUserInfo:
    """第三方平台规范化后的用户信息"""

    provider_uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    raw: dict = field(default_factory=dict)


class SocialProviderAdapter(ABC):
    """第三方 OAuth2 适配器接口

    内置实现：GitHubAdapter / GoogleAdapter / GenericAdapter（通用 OAuth2，
    覆盖微信/Gitee 等，平台 URL 由 OauthProvider 配置提供）。
    """

    name: str = ""

    @abstractmethod
    def build_authorize_url(
        self, provider: Any, state: str, redirect_uri: str,
    ) -> str:
        """构建平台授权页 URL（含 state 与 redirect_uri）"""

    @abstractmethod
    async def exchange_token(
        self, provider: Any, code: str, redirect_uri: str,
    ) -> str:
        """授权码换取 access_token"""

    @abstractmethod
    async def fetch_userinfo(self, provider: Any, access_token: str) -> dict:
        """拉取平台用户信息（原始 JSON）"""

    @abstractmethod
    def normalize(self, raw: dict) -> SocialUserInfo:
        """原始用户信息 → 统一结构（字段映射完成后调用）"""
