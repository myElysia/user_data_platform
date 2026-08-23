"""社交适配器注册表 — 内置平台直取，未内置平台走通用适配器"""

from app.infrastructure.social.base import SocialProviderAdapter
from app.infrastructure.social.generic import GenericAdapter
from app.infrastructure.social.github import GitHubAdapter
from app.infrastructure.social.google import GoogleAdapter

BUILTIN_ADAPTERS: dict[str, type[SocialProviderAdapter]] = {
    GitHubAdapter.name: GitHubAdapter,
    GoogleAdapter.name: GoogleAdapter,
}


def get_adapter(name: str) -> SocialProviderAdapter:
    """按平台名称获取适配器实例（未内置平台使用通用 OAuth2 适配器）"""
    adapter_cls = BUILTIN_ADAPTERS.get(name)
    if adapter_cls is not None:
        return adapter_cls()
    return GenericAdapter(name)
