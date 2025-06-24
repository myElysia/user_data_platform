from sqlmodel import SQLModel

from app.models.user import (
    User,
)
from app.models.audit import (
    AuditLog,
    TransformLog
)
from app.models.auth import (
    CasbinRule,
    CasbinSystem,
    CasbinRole,
    OauthProvider,
    OauthAccount,
    OAuthState,
    SSOSession,
    MFASecuity,
    RevokedToken,
    FieldMapping
)
from app.models.setting import (
    SecurityPolicy
)

METADATA = SQLModel.metadata
