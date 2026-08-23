"""SMS 短信发送 — 未配置短信网关时降级为日志输出（开发模式）

真实短信网关（阿里云/腾讯云/Twilio 等）接入时，在
`_send_via_provider` 中实现对应 SDK 调用即可。
"""

from app.infrastructure.config import SmsSettings
from app.infrastructure.log import AsyncLogger

_logger = AsyncLogger.get_logger(**{"name": "sms_sender"})


async def send_verification_sms(phone: str, code: str, purpose: str = "phone_verify") -> None:
    """发送验证码短信

    - SMS 网关已配置（SMS_ACCESS_KEY + SMS_SECRET）→ 走网关发送
    - 未配置 → 打印到日志（开发模式降级）
    """
    settings = SmsSettings()

    if not settings.is_configured:
        await _logger.warning(
            f"[SMS-DEGRADED] 短信网关未配置，验证码仅记录日志 | "
            f"to={phone} purpose={purpose} code={code}",
        )
        return

    try:
        await _send_via_provider(settings, phone, code, purpose)
        await _logger.info(f"验证码短信已发送: to={phone} purpose={purpose}")
    except Exception as exc:
        await _logger.error(f"验证码短信发送失败: to={phone} error={exc}")
        raise


async def _send_via_provider(settings: SmsSettings, phone: str, code: str, purpose: str) -> None:
    """真实短信网关调用（TODO：接入阿里云/腾讯云等 SDK）"""
    raise NotImplementedError(
        "SMS provider integration not implemented; "
        "configure gateway SDK in app.infrastructure.sms.sms_sender._send_via_provider"
    )
