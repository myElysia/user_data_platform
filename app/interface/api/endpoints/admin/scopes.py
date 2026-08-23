"""管理员端点 — OAuth Scope 管理"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.database import get_db_session
from app.infrastructure.persistence.models.oauth import OAuthScope

router = APIRouter(prefix="/admin/scopes", tags=["Admin - OAuth Scopes"])


async def _admin_audit(session, action: str, new_value: str) -> None:
    """管理员操作审计（user_id=0 表示系统管理员操作）"""
    from app.application.audit_service import record_audit

    await record_audit(
        session, 0, action, ip_address="admin",
        operation_type="ADMIN", target_resource_id=0,
        new_value=new_value,
    )


@router.get("")
async def list_scopes(
    session: AsyncSession = Depends(get_db_session),
):
    """列出所有 Scope 定义"""
    result = await session.exec(select(OAuthScope))
    scopes = result.all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "category": s.category,
            "is_default": s.is_default,
            "is_sensitive": s.is_sensitive,
        }
        for s in scopes
    ]


@router.post("", status_code=201)
async def create_scope(
    name: str,
    description: str,
    category: str = None,
    is_default: bool = False,
    is_sensitive: bool = False,
    session: AsyncSession = Depends(get_db_session),
):
    """创建新的 Scope"""
    existing = await session.exec(
        select(OAuthScope).where(OAuthScope.name == name)
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="Scope already exists")

    scope = OAuthScope(
        name=name,
        description=description,
        category=category,
        is_default=is_default,
        is_sensitive=is_sensitive,
    )
    session.add(scope)
    await session.commit()
    await _admin_audit(session, "admin_scope_create", name)
    return {"message": "Scope created", "name": name}


@router.delete("/{scope_name}")
async def delete_scope(
    scope_name: str,
    session: AsyncSession = Depends(get_db_session),
):
    """删除 Scope"""
    result = await session.exec(
        select(OAuthScope).where(OAuthScope.name == scope_name)
    )
    scope = result.first()
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")

    await session.delete(scope)
    await session.commit()
    await _admin_audit(session, "admin_scope_delete", scope_name)
    return {"message": f"Scope '{scope_name}' deleted"}