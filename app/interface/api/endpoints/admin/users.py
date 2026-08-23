"""管理员端点 — 用户管理 CRUD"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models import User
from app.domain.identity.services import hash_password
from app.domain.identity.services import PasswordPolicy
from app.interface.api.schemas.admin import (
    AdminUserUpdateRequest,
    AdminBatchDeleteRequest,
)

router = APIRouter(prefix="/admin/users", tags=["Admin - Users"])


async def _admin_audit(
    session: AsyncSession,
    action: str,
    target_resource_id: int,
    old_value: str = None,
    new_value: str = None,
) -> None:
    """管理员操作审计（user_id=0 表示系统管理员操作）"""
    from app.application.audit_service import record_audit

    await record_audit(
        session, 0, action, ip_address="admin",
        operation_type="ADMIN", target_resource_id=target_resource_id,
        old_value=old_value, new_value=new_value,
    )


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "phone": user.phone,
        "country": user.country,
        "language": user.language,
        "email_verified": user.email_verified,
        "phone_verified": user.phone_verified,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
    }


@router.get("")
async def list_users(
    session: AsyncSession = Depends(get_db_session),
    skip: int = 0,
    limit: int = 50,
    email: str = "",
    is_active: bool = None,
):
    """列出所有用户（管理员视角）"""
    query = select(User)

    if email:
        query = query.where(User.email.contains(email))
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # 总数
    count_result = await session.exec(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.one()

    query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
    result = await session.exec(query)
    users = result.all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "users": [_user_to_dict(u) for u in users],
    }


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """获取用户详情"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.put("/{user_id}/toggle")
async def toggle_user_active(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """启用/禁用用户"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old = user.is_active
    user.is_active = not user.is_active
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    await session.commit()

    await _admin_audit(session, "admin_user_toggle", user_id,
                       old_value=str(old), new_value=str(user.is_active))

    return {
        "message": f"User {'activated' if user.is_active else 'deactivated'}",
        "is_active": user.is_active,
    }


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: AdminUserUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """更新用户信息（管理员）

    邮箱变更 → 重置 email_verified 并经 ARQ 异步发送邮箱验证码；
    手机号变更 → 重置 phone_verified 并经 ARQ 异步发送短信验证码。
    邮箱/手机号未发生变动时不触发任何验证发送（大小写不敏感比较，
    空串与 NULL 视为等价）。验证码发送失败不阻断保存（限流等场景），
    结果通过 verification 字段返回。
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    verification_msgs = []

    # 邮箱：大小写不敏感比较（EmailStr 校验会将域名部分小写化，
    # 与库中原值直接比较可能误判变更 → 误触发验证发送）
    email_changed = (
        body.email is not None
        and body.email.lower() != (user.email or "").lower()
    )
    if email_changed:
        existing = await session.exec(
            select(User).where(User.email == body.email, User.id != user_id)
        )
        if existing.first():
            raise HTTPException(status_code=409, detail="Email already in use")
        user.email = body.email
        user.email_verified = False
        verification_msgs.extend(
            await _send_verification(session, body.email, "email_verify", "email")
        )

    if body.display_name is not None:
        user.display_name = body.display_name

    # 手机号：空串与 NULL 视为等价（前端未填手机号时传空串，
    # 不应误判为变更而重置 phone_verified）
    new_phone = (body.phone or "").strip() if body.phone is not None else None
    old_phone = (user.phone or "").strip()
    if new_phone is not None and new_phone != old_phone:
        if new_phone:
            existing_phone = await session.exec(
                select(User).where(User.phone == new_phone, User.id != user_id)
            )
            if existing_phone.first():
                raise HTTPException(status_code=409, detail="Phone already in use")
        user.phone = new_phone or None
        user.phone_verified = False
        if new_phone:
            verification_msgs.extend(
                await _send_verification(session, new_phone, "phone_verify", "phone")
            )

    if body.country is not None:
        user.country = body.country
    if body.language is not None:
        user.language = body.language

    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    await _admin_audit(session, "admin_user_update", user_id,
                       new_value=f"verification:{','.join(verification_msgs)}" if verification_msgs else None)

    result = _user_to_dict(user)
    if verification_msgs:
        result["verification"] = {"sent": verification_msgs}
    return result


async def _send_verification(
    session: AsyncSession,
    target: str,
    purpose: str,
    channel: str,
) -> list:
    """保存后触发验证码发送（ARQ 入队，发送失败不阻断保存）"""
    from app.application.verification_use_cases import verification_use_cases

    try:
        res = await verification_use_cases.request_code(
            session, target, purpose, "admin", channel=channel,
        )
        return [f"{channel} verification sent ({res['mode']})"]
    except HTTPException as exc:
        return [f"{channel} verification skipped: {exc.detail}"]


@router.put("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    new_password: str,
    session: AsyncSession = Depends(get_db_session),
):
    """重置用户密码（管理员）"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    PasswordPolicy.validate(new_password)
    user.password = hash_password(new_password)
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    await session.commit()

    await _admin_audit(session, "admin_user_reset_password", user_id)

    return {"message": "Password reset successfully"}


@router.delete("/batch")
async def batch_delete_users(
    body: AdminBatchDeleteRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """批量软删除用户（is_active=False + deleted_at）"""
    result = await session.exec(
        select(User).where(User.id.in_(body.user_ids))
    )
    users = result.all()
    deleted = []
    for user in users:
        if not user.deleted_at:
            user.is_active = False
            user.deleted_at = datetime.now(timezone.utc)
            user.updated_at = datetime.now(timezone.utc)
            session.add(user)
            deleted.append(user.id)
    await session.commit()

    await _admin_audit(
        session, "admin_user_batch_delete", 0,
        new_value=f"user_ids:{','.join(map(str, deleted))}",
    )

    return {"message": f"{len(deleted)} users deactivated", "deleted_ids": deleted}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """软删除用户"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)
    session.add(user)
    await session.commit()

    await _admin_audit(session, "admin_user_delete", user_id)

    return {"message": "User deactivated"}