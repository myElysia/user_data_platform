"""SMTP 邮件发送 — 未配置 SMTP 时降级为日志输出（开发模式）"""

import aiosmtplib

from app.infrastructure.config import MailSettings
from app.infrastructure.log import AsyncLogger

_logger = AsyncLogger.get_logger(**{"name": "mailer"})

PURPOSE_SUBJECTS = {
    "email_verify": "邮箱验证码",
    "2fa_backup": "双因素认证备用验证码",
    "risk_challenge": "安全挑战验证码",
}


async def send_verification_mail(email: str, code: str, purpose: str = "email_verify") -> None:
    """发送验证码邮件

    - SMTP 已配置（SMTP_HOST + SMTP_FROM）→ aiosmtplib 发送
    - SMTP 未配置 → 打印到日志（开发模式降级）
    """
    settings = MailSettings()
    subject = PURPOSE_SUBJECTS.get(purpose, "验证码")

    if not settings.is_configured:
        await _logger.warning(
            f"[MAIL-DEGRADED] SMTP 未配置，验证码仅记录日志 | "
            f"to={email} purpose={purpose} code={code}",
        )
        return

    message = aiosmtplib.EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message["Subject"] = f"[UserPlatform] {subject}"
    message.set_content(f"您的验证码是：{code}（10 分钟内有效）。若非本人操作请忽略。")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_USE_TLS,
            timeout=settings.SMTP_TIMEOUT,
        )
        await _logger.info(f"验证码邮件已发送: to={email} purpose={purpose}")
    except Exception as exc:
        await _logger.error(f"验证码邮件发送失败: to={email} error={exc}")
        raise
