"""安全域值对象 — DeviceFingerprint/RiskScore(0-100)/RiskAction 枚举"""

from dataclasses import dataclass
from enum import Enum


class RiskAction(str, Enum):
    """风险判定动作"""

    ALLOW = "ALLOW"
    CHALLENGE_2FA = "CHALLENGE_2FA"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class RiskScore:
    """风险评分值对象（0-100）"""

    value: int

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 100:
            raise ValueError(f"Risk score must be 0-100, got {self.value}")

    @property
    def action(self) -> RiskAction:
        """按阈值判定动作：<40 放行，40-70 挑战 2FA，>70 阻断"""
        if self.value < 40:
            return RiskAction.ALLOW
        if self.value <= 70:
            return RiskAction.CHALLENGE_2FA
        return RiskAction.BLOCK


@dataclass(frozen=True)
class DeviceFingerprint:
    """设备指纹值对象 — SHA256(ip|ua|accept-language|...) 哈希"""

    hash: str

    def __str__(self) -> str:
        return self.hash
