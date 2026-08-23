"""社交登录与平台配置请求/响应模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

HTTPS_PATTERN = r"^https?://.+$"


class SocialAccountResponse(BaseModel):
    """绑定社交账号视图"""
    id: int
    provider: str
    provider_uid: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Admin 平台配置
# ---------------------------------------------------------------------------

class ProviderCreateRequest(BaseModel):
    """创建第三方平台配置请求（client_secret 加密存储）"""
    name: str = Field(..., max_length=50)
    client_id: str = Field(..., max_length=255)
    client_secret: str = Field(..., max_length=500)
    authorization_url: str = Field("", pattern=HTTPS_PATTERN)
    token_url: Optional[str] = Field("", pattern=HTTPS_PATTERN)
    userinfo_url: Optional[str] = Field("", pattern=HTTPS_PATTERN)
    scope: str = ""
    provider_type: str = "oauth"
    grant_type: str = "authorization_code"
    additional_auth_params: dict = {}
    is_active: bool = True


class ProviderUpdateRequest(BaseModel):
    """更新第三方平台配置请求（仅提供的字段生效）"""
    client_id: Optional[str] = Field(None, max_length=255)
    client_secret: Optional[str] = Field(None, max_length=500)
    authorization_url: Optional[str] = Field(None, pattern=HTTPS_PATTERN)
    token_url: Optional[str] = Field(None, pattern=HTTPS_PATTERN)
    userinfo_url: Optional[str] = Field(None, pattern=HTTPS_PATTERN)
    scope: Optional[str] = None
    additional_auth_params: Optional[dict] = None
    is_active: Optional[bool] = None


class ProviderResponse(BaseModel):
    """平台配置视图（client_secret 脱敏）"""
    id: int
    name: str
    icon: Optional[str] = None
    provider_type: str
    grant_type: str
    client_id: str
    client_secret_masked: str = ""
    authorization_url: str
    token_url: Optional[str] = None
    userinfo_url: Optional[str] = None
    scope: str = ""
    additional_auth_params: dict = {}
    is_active: bool = True
    config_status: bool = False
    login_count: int = 0
    last_success_at: Optional[datetime] = None
    created_at: datetime
