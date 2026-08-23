"""基础设施层社交 — 第三方 OAuth 适配器（GitHub/Google/通用）"""

from app.infrastructure.social.base import SocialProviderAdapter, SocialUserInfo
from app.infrastructure.social.registry import get_adapter

__all__ = ["SocialProviderAdapter", "SocialUserInfo", "get_adapter"]
