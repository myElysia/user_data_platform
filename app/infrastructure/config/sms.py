from functools import cached_property

from app.infrastructure.config.base import EnvSettings


class SmsSettings(EnvSettings):
    """SMS 短信发送配置 — 未配置网关密钥时短信降级为日志输出"""

    SMS_ACCESS_KEY: str = ""
    SMS_SECRET: str = ""
    SMS_SIGN_NAME: str = ""
    SMS_TEMPLATE_CODE: str = ""

    @cached_property
    def prefix(self):
        return "SMS_"

    @property
    def is_configured(self) -> bool:
        """短信网关是否已配置（未配置 → 短信降级为日志输出）"""
        return bool(self.SMS_ACCESS_KEY and self.SMS_SECRET)
