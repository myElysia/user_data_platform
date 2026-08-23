from fastapi import APIRouter

from app.interface.api.endpoints.user import router as user_router
from app.interface.api.endpoints.oidc.discovery import router as discovery_router
from app.interface.api.endpoints.oidc.jwks import router as jwks_router
from app.interface.api.endpoints.oidc.authorize import router as authorize_router
from app.interface.api.endpoints.oidc.token import router as token_router
from app.interface.api.endpoints.oidc.userinfo import router as userinfo_router
from app.interface.api.endpoints.oidc.register import router as register_router
from app.interface.api.endpoints.oidc.introspection import router as introspection_router
from app.interface.api.endpoints.admin.clients import router as admin_clients_router
from app.interface.api.endpoints.admin.scopes import router as admin_scopes_router
from app.interface.api.endpoints.admin.users import router as admin_users_router
from app.interface.api.endpoints.webhook_endpoints import router as webhook_router
from app.interface.api.endpoints.rate_limit_status import router as ratelimit_router
from app.interface.api.endpoints.auth import router as auth_router
from app.interface.api.endpoints.consent import router as consent_router
from app.interface.api.endpoints.mfa import router as mfa_router
from app.interface.api.endpoints.social import router as social_router
from app.interface.api.endpoints.verification import router as verification_router
from app.interface.api.endpoints.devices import router as devices_router
from app.interface.api.endpoints.admin.providers import router as admin_providers_router
from app.interface.api.endpoints.admin.audit import router as admin_audit_router

router = APIRouter(
    prefix="/api",
    tags=["api"],
)

# 用户端点
router.include_router(user_router)
router.include_router(auth_router)
router.include_router(mfa_router)
router.include_router(social_router)
router.include_router(verification_router)
router.include_router(devices_router)
router.include_router(consent_router)

# OIDC 端点（无 /api 前缀，直接挂载到根路径）
oidc_router = APIRouter(tags=["OIDC"])
oidc_router.include_router(discovery_router)
oidc_router.include_router(jwks_router)
oidc_router.include_router(authorize_router)
oidc_router.include_router(token_router)
oidc_router.include_router(userinfo_router)
oidc_router.include_router(register_router)
oidc_router.include_router(introspection_router)

# 管理端点
admin_router = APIRouter(prefix="/api", tags=["Admin"])
admin_router.include_router(admin_clients_router)
admin_router.include_router(admin_scopes_router)
admin_router.include_router(webhook_router)
admin_router.include_router(admin_users_router)
admin_router.include_router(admin_providers_router)
admin_router.include_router(admin_audit_router)
admin_router.include_router(ratelimit_router)

__all__ = ["router", "oidc_router", "admin_router"]
