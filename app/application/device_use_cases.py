"""设备管理用例 — 列表/信任/撤销（第八阶段：设备指纹绑定）"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.persistence.models import DeviceFingerprint, SSOSession

TRUSTED_SCORE = 0.8


class DeviceUseCases:
    """设备信任管理用例"""

    async def list_devices(
        self, session: AsyncSession, user_id: int,
        current_fp: str = "",
    ) -> list[dict]:
        """列出用户所有设备，标记当前设备"""
        result = await session.exec(
            select(DeviceFingerprint).where(
                DeviceFingerprint.user_id == user_id,
            ).order_by(DeviceFingerprint.last_seen.desc())
        )
        devices = result.all()
        return [
            {
                "id": d.id,
                "fingerprint_hash": d.fingerprint_hash,
                "trust_score": d.trust_score,
                "is_trusted": d.is_trusted,
                "verification_count": d.verification_count,
                "device_info": d.device_info,
                "first_seen": d.first_seen,
                "last_seen": d.last_seen,
                "is_current": d.fingerprint_hash == current_fp,
            }
            for d in devices
        ]

    async def trust_device(
        self, session: AsyncSession, user_id: int, device_id: int,
    ) -> dict:
        """信任设备 — 信任分提升至 0.8，标记 is_trusted"""
        device = await session.get(DeviceFingerprint, device_id)
        if device is None or device.user_id != user_id:
            raise HTTPException(status_code=404, detail="Device not found")

        device.trust_score = TRUSTED_SCORE
        device.is_trusted = True
        session.add(device)
        await session.commit()
        return {
            "message": "Device trusted",
            "trust_score": device.trust_score,
            "is_trusted": device.is_trusted,
        }

    async def revoke_device(
        self, session: AsyncSession, user_id: int, device_id: int,
    ) -> dict:
        """撤销设备 — 删除设备记录 + 撤销所有关联活跃会话"""
        device = await session.get(DeviceFingerprint, device_id)
        if device is None or device.user_id != user_id:
            raise HTTPException(status_code=404, detail="Device not found")

        # 撤销该设备指纹的所有活跃会话
        sessions = await session.exec(
            select(SSOSession).where(
                SSOSession.device_fingerprint == device.fingerprint_hash,
                SSOSession.is_active == True,  # noqa: E712
            )
        )
        revoked = 0
        for sso in sessions.all():
            sso.is_active = False
            session.add(sso)
            revoked += 1

        await session.delete(device)
        await session.commit()
        return {
            "message": "Device revoked",
            "sessions_revoked": revoked,
        }


# 模块级单例
device_use_cases = DeviceUseCases()