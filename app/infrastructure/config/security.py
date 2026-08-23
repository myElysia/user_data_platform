from functools import cached_property

from app.infrastructure.config.base import EnvSettings


class SecuritySettings(EnvSettings):
    """安全配置 — 风险评估引擎（第九阶段）"""

    # 高风险 IP 黑名单（逗号分隔），命中 +50 分直接判定 BLOCK
    RISK_IP_BLACKLIST: str = ""

    @cached_property
    def prefix(self):
        return "RISK_"

    @property
    def blacklisted_ips(self) -> set[str]:
        """黑名单 IP 集合（去空白、去空项）"""
        return {
            item.strip()
            for item in self.RISK_IP_BLACKLIST.split(",")
            if item.strip()
        }
