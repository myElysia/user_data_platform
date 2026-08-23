"""OIDC / OAuth 2.0 协议请求与响应模型"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# OIDC Discovery
# ---------------------------------------------------------------------------

class DiscoveryResponse(BaseModel):
    """OIDC Discovery 响应"""
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    registration_endpoint: str | None = None
    scopes_supported: list[str]
    response_types_supported: list[str]
    grant_types_supported: list[str]
    subject_types_supported: list[str]
    id_token_signing_alg_values_supported: list[str]
    token_endpoint_auth_methods_supported: list[str]
    claims_supported: list[str]
    code_challenge_methods_supported: list[str] | None = None


# ---------------------------------------------------------------------------
# Authorization Endpoint
# ---------------------------------------------------------------------------

class AuthorizeRequest(BaseModel):
    """GET /authorize 请求参数"""
    response_type: str = Field(..., description="code, token, id_token")
    client_id: str
    redirect_uri: str
    scope: str = "openid"
    state: str | None = None
    nonce: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str | None = "S256"
    prompt: str | None = None


# ---------------------------------------------------------------------------
# Token Endpoint
# ---------------------------------------------------------------------------

class TokenRequest(BaseModel):
    """POST /token 请求"""
    grant_type: str = Field(..., description="authorization_code, client_credentials, refresh_token")
    code: str | None = None
    redirect_uri: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    code_verifier: str | None = None
    scope: str | None = None


class TokenResponse(BaseModel):
    """POST /token 响应"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str | None = None


class TokenErrorResponse(BaseModel):
    """Token 端点错误响应"""
    error: str
    error_description: str | None = None


# ---------------------------------------------------------------------------
# Token Revocation (RFC 7009)
# ---------------------------------------------------------------------------

class RevokeRequest(BaseModel):
    """POST /token/revoke 请求"""
    token: str
    token_type_hint: str | None = None


# ---------------------------------------------------------------------------
# UserInfo
# ---------------------------------------------------------------------------

class UserInfoResponse(BaseModel):
    """UserInfo 响应"""
    sub: str
    name: str | None = None
    preferred_username: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    phone_number: str | None = None
    phone_number_verified: bool | None = None
    picture: str | None = None
    locale: str | None = None


# ---------------------------------------------------------------------------
# Client Registration (RFC 7591)
# ---------------------------------------------------------------------------

class ClientRegisterRequest(BaseModel):
    """POST /register 请求"""
    client_name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    redirect_uris: list[str] = Field(default_factory=list)
    grant_types: list[str] = Field(default_factory=lambda: ["authorization_code"])
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    token_endpoint_auth_method: str = "client_secret_basic"
    homepage_url: str | None = None
    logo_url: str | None = None


class ClientUpdateRequest(BaseModel):
    """PUT /register/{client_id} 请求"""
    client_name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    redirect_uris: list[str] | None = None
    grant_types: list[str] | None = None
    scopes: list[str] | None = None
    homepage_url: str | None = None
    logo_url: str | None = None
    is_active: bool | None = None


class ClientResponse(BaseModel):
    """客户端注册/查询响应"""
    client_id: str
    client_name: str
    description: str | None = None
    redirect_uris: list[str] = []
    grant_types: list[str] = []
    scopes: list[str] = []
    homepage_url: str | None = None
    logo_url: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class ClientSecretResponse(BaseModel):
    """客户端密钥响应（仅注册时返回）"""
    client_id: str
    client_secret: str
    client_name: str
    description: str | None = None
    redirect_uris: list[str] = []
    grant_types: list[str] = []
    scopes: list[str] = []
    homepage_url: str | None = None
    logo_url: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

class ConsentRequest(BaseModel):
    """用户同意请求"""
    client_id: str
    scopes: list[str]


class ConsentResponse(BaseModel):
    """用户同意响应"""
    user_id: int
    client_id: str
    scopes: list[str]
    granted_at: datetime
    expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class OAuthErrorResponse(BaseModel):
    """OAuth 2.0 标准错误响应"""
    error: str
    error_description: str | None = None
    error_uri: str | None = None
    state: str | None = None