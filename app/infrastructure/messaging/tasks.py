"""ARQ 任务函数注册表

Worker 进程（python main.py worker）按 TASKS 注册表执行；
Redis 不可用时 dispatcher 降级为进程内直接调用同一函数（ctx 传 None）。
"""

from typing import Callable, Dict


async def send_verification_email(
    ctx, email: str, code: str, purpose: str = "email_verify",
) -> None:
    """发送验证码邮件（邮箱验证 / 2FA 备用 / 风险挑战）

    ctx 为 ARQ 任务上下文；进程内降级执行时为 None。
    """
    from app.infrastructure.mail.mailer import send_verification_mail

    await send_verification_mail(email, code, purpose)


async def send_phone_verification(
    ctx, phone: str, code: str, purpose: str = "phone_verify",
) -> None:
    """发送验证码短信（手机号验证）

    ctx 为 ARQ 任务上下文；进程内降级执行时为 None。
    """
    from app.infrastructure.sms.sms_sender import send_verification_sms

    await send_verification_sms(phone, code, purpose)


TASKS: Dict[str, Callable] = {
    "send_verification_email": send_verification_email,
    "send_phone_verification": send_phone_verification,
}
