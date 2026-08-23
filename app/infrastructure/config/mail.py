from functools import cached_property

from app.infrastructure.config.base import EnvSettings

SELF_DOMAINS = [
    "arknights.top",
    "shinestar.fun",
]

MAIL_DOMAINS = [
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "live.com",
    "163.com",
    "126.com",
    "qq.com",
    "outlook.com",
]


class MailSettings(EnvSettings):
    """SMTP 邮件发送配置 — 未配置 SMTP_HOST 时邮件降级为日志输出"""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT: int = 15

    @cached_property
    def prefix(self):
        return "SMTP_"

    @property
    def is_configured(self) -> bool:
        """SMTP 是否已配置（未配置 → 邮件降级为日志输出）"""
        return bool(self.SMTP_HOST and self.SMTP_FROM)
