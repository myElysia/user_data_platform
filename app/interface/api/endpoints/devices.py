"""设备管理端点 — 列表/信任/撤销（第八阶段：设备指纹绑定）

路由前缀 /api/v1/devices：
- GET    /            我的设备列表（标记当前设备）
- POST   /{id}/trust  信任设备（信任分提升至 0.8）
- DELETE /{id}        撤销设备 + 撤销该设备所有活跃会话
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.device_use_cases import device_use_cases
from app.infrastructure.database import get_db_session
from app.interface.api.deps.auth import get_current_user_id

router = APIRouter(prefix="/v1/devices", tags=["Devices"])


@router.get("")
async def list_devices(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """我的设备列表 — 按当前请求指纹标记当前设备"""
    current_fp = await _current_fingerprint(request)
    return await device_use_cases.list_devices(session, user_id, current_fp)


@router.post("/{device_id}/trust")
async def trust_device(
    device_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """信任设备 — 信任分提升至 0.8"""
    result = await device_use_cases.trust_device(session, user_id, device_id)
    await _audit(session, user_id, "device_trusted", request, device_id)
    return result


@router.delete("/{device_id}")
async def revoke_device(
    device_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """撤销设备 — 删除记录并撤销该设备所有活跃会话"""
    result = await device_use_cases.revoke_device(session, user_id, device_id)
    await _audit(session, user_id, "device_revoked", request, device_id)
    return result


async def _current_fingerprint(request: Request) -> str:
    """计算当前请求的设备指纹（与登录指纹同算法）"""
    from app.infrastructure.persistence.models import SSOSession
    return SSOSession.generate_device_fingerprint(request)


async def _audit(
    session: AsyncSession, user_id: int, action: str,
    request: Request, device_id: int,
) -> None:
    from app.application.audit_service import record_audit

    ip = request.client.host if request.client else "unknown"
    await record_audit(
        session, user_id, action, ip_address=ip,
        operation_type="DEVICE", target_resource_id=device_id,
        request_metadata={"user_agent": request.headers.get("user-agent", "")},
    )
