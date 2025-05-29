from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, DateTime, func, JSON
from sqlmodel import SQLModel, Field, Relationship

from app.local.settings import Settings

settings = Settings()


class TransformLog(SQLModel, table=True, table_description="FieldMapping审计日志"):
    __tablename__ = f"{settings.APP_NAME}_transform_log"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    created_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False),
                                 title="更新时间")
    rule: str
    input_value: str
    output_value: str
    is_error: bool
    error_msg: str


class AuditLog(SQLModel, table=True, table_description="系统审计日志"):
    __tablename__ = f"{settings.APP_NAME}_audit_log"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        ),
        title="更新时间"
    )
    user: "User" = Relationship(back_populates="audit_logs")
    user_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_user.id")
    action: str
    ip_address: str
    target_resource_id: Optional[int]  # 操作的目标资源ID（如被修改的用户ID）
    request_metadata: dict = Field(sa_column=Column(JSON))  # 请求头、UA、设备信息
    operation_type: str  # CREATE/UPDATE/DELETE等
    old_value: Optional[str]  # 修改前的值（如角色变更前）
    new_value: Optional[str]  # 修改后的值
