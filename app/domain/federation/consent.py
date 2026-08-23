"""联邦域同意判定 — 纯逻辑（零框架依赖）

由原 app/core/consent.py 拆分：
- 纯判定逻辑（是否需要同意、scope 合并）保留在本模块
- DB 操作部分（ConsentManager）迁至 application 层（application/oauth_services.py）
"""

from typing import List, Optional


def decide_consent_needed(
    consent_scopes: Optional[List[str]],
    is_expired: bool,
    requested_scopes: List[str],
) -> bool:
    """判断是否需要用户同意

    - 从未授权（consent_scopes 为 None）→ 需要
    - 授权已过期 → 需要
    - 存在未覆盖的 scope → 需要
    """
    if consent_scopes is None:
        return True
    if is_expired:
        return True
    return any(s not in consent_scopes for s in requested_scopes)


def merge_scopes(
    existing_scopes: Optional[List[str]],
    granted_scopes: List[str],
) -> List[str]:
    """合并已授权 scope 与新授权 scope（去重保序）"""
    merged: List[str] = []
    for scope in list(existing_scopes or []) + list(granted_scopes):
        if scope not in merged:
            merged.append(scope)
    return merged


def scope_descriptions(
    requested_scopes: List[str],
    known: dict[str, str],
) -> List[dict]:
    """生成同意页展示用 scope 列表（{name, description}）"""
    return [
        {"name": s, "description": known.get(s, s)}
        for s in requested_scopes
    ]
