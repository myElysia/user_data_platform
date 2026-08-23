"""管理员端点请求模型"""

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class AdminUserUpdateRequest(BaseModel):
    """管理员更新用户信息（全部可选，仅更新传入字段）"""
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=255)
    country: Optional[str] = None
    language: Optional[str] = None


class AdminBatchDeleteRequest(BaseModel):
    """批量软删除用户"""
    user_ids: List[int] = Field(..., min_length=1, max_length=100)
