from sqlmodel import SQLModel

from app.infrastructure.persistence.models.user import (
    User,
)
from app.infrastructure.persistence.models.audit import (
    AuditLog,
    TransformLog
)
from app.infrastructure.persistence.models.auth import (
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
from app.infrastructure.persistence.models.setting import (
    SecurityPolicy
)
from app.infrastructure.persistence.models.oauth import (
    OAuthClient,
    OAuthScope,
    UserConsent,
    OAuthToken,
    DeviceFingerprint,
    GrantTypeEnum,
    TokenTypeEnum,
    ClientAuthMethod,
)
from app.infrastructure.persistence.models.webhook import (
    WebhookConfig,
    WebhookDelivery,
    WebhookEventType,
    WebhookDeliveryStatus,
)
from app.infrastructure.persistence.models.security import (
    VerificationCode,
    RiskEvent,
    AuthorizationCode,
)

METADATA = SQLModel.metadata
