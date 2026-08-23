"""风险引擎用例 — 登录风险评估编排/事件查询/当前状态（第九阶段）

领域层 RiskAssessmentService（纯规则引擎）已就绪，本用例负责：
- 收集评估上下文（新设备/新 IP/失败计数/短时多 IP/黑名单）→ 执行评估 → RiskEvent 落库
- 管理员分页查询风险事件
- 当前会话风险状态查询（按用户 + 设备指纹）
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.security.services import RiskAssessmentService, RiskContext
from app.infrastructure.config.security import SecuritySettings
from app.infrastructure.persistence.models import (
    DeviceFingerprint,
    RiskEvent,
    SSOSession,
    User,
)

RECENT_IP_WINDOW = timedelta(hours=24)  # 短时间多 IP 切换观察窗口


class RiskUseCases:
    """风险评估用例编排"""

    async def assess_login(
        self,
        session: AsyncSession,
        user: User,
        request: Request,
    ) -> str:
        """登录风险评估 → 落库 RiskEvent → 返回判定动作

        返回 "ALLOW" / "CHALLENGE_2FA" / "BLOCK"。
        """
        ip = request.client.host if request.client else "unknown"
        fp = SSOSession.generate_device_fingerprint(request)

        # 新设备：该用户从未在此指纹上登录过
        dev_result = await session.exec(
            select(DeviceFingerprint).where(
                DeviceFingerprint.user_id == user.id,
                DeviceFingerprint.fingerprint_hash == fp,
            )
        )
        is_new_device = dev_result.first() is None

        # 新 IP：该用户历史会话从未出现过该 IP
        ip_result = await session.exec(
            select(SSOSession).where(
                SSOSession.user_id == user.id,
                SSOSession.ip_address == ip,
            )
        )
        is_new_ip = ip_result.first() is None

        # 登录失败次数（缓存，15 分钟窗口，auth_use_cases 写入）
        from app.infrastructure.cache import get_cache_backend
        backend = await get_cache_backend()
        failed = int(await backend.get(f"login_fail:{user.email}") or 0)

        # 短时间（24h）内出现过的 IP 数量（含当前）
        since = datetime.now(timezone.utc) - RECENT_IP_WINDOW
        recent_result = await session.exec(
            select(SSOSession.ip_address, SSOSession.created_at).where(
                SSOSession.user_id == user.id,
            )
        )
        recent_ips: set[str] = {ip}
        for hist_ip, created_at in recent_result.all():
            created = created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= since:
                recent_ips.add(hist_ip)

        # 黑名单 IP（配置驱动）
        is_blacklisted = ip in SecuritySettings().blacklisted_ips

        assessment = RiskAssessmentService.assess(RiskContext(
            ip=ip,
            is_new_device=is_new_device,
            is_new_ip=is_new_ip,
            failed_attempts=failed,
            recent_ip_count=len(recent_ips),
            is_blacklisted_ip=is_blacklisted,
        ))

        # 风险事件落库（含 ALLOW 的全程记录，供审计与查询）
        session.add(RiskEvent(
            user_id=user.id,
            email=user.email,
            ip=ip,
            device_fingerprint=fp,
            score=assessment.score,
            triggered_rules=assessment.triggered_rules,
            action=assessment.action,
        ))
        await session.commit()

        return assessment.action

    async def list_events(
        self,
        session: AsyncSession,
        *,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[RiskEvent]]:
        """分页查询风险事件（倒序），可按用户过滤"""
        conditions = []
        if user_id is not None:
            conditions.append(RiskEvent.user_id == user_id)

        query = select(RiskEvent)
        for cond in conditions:
            query = query.where(cond)

        count_query = select(RiskEvent)
        for cond in conditions:
            count_query = count_query.where(cond)
        total = len((await session.exec(count_query)).all())

        events = (await session.exec(
            query.order_by(RiskEvent.id.desc()).offset(skip).limit(limit)
        )).all()
        return total, list(events)

    async def current_status(
        self,
        session: AsyncSession,
        user_id: int,
        fingerprint: str,
    ) -> Optional[RiskEvent]:
        """当前会话风险状态 — 该用户最近一次风险评估事件"""
        result = await session.exec(
            select(RiskEvent)
            .where(RiskEvent.user_id == user_id)
            .order_by(RiskEvent.id.desc())
            .limit(1)
        )
        return result.first()


# 模块级单例
risk_use_cases = RiskUseCases()
