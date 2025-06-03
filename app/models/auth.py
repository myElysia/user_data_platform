from ast import parse, NodeTransformer, Name
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
from types import MappingProxyType
from typing import Optional, List

from sqlalchemy import Index, Column, Integer, String, DateTime, func, UniqueConstraint, JSON, Boolean
from sqlalchemy_utils import StringEncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import FernetEngine
from sqlmodel import SQLModel, Field, Relationship
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from app.local.settings import Settings
from app.models.audit import TransformLog
from app.utils.security import generate_random_string

settings = Settings()

HTTPS_REGEX = r"^https?://.+"


class ProvideTypeEnum(str, Enum):
    # 认证方式
    Oauth = "oauth"
    Saml = "saml"
    Oidc = "oidc"


class GrantType(str, Enum):
    """
    授权方式
    """
    AUTHORIZATION_CODE = "authorization_code"
    IMPLICIT = "implicit"
    PASSWORD = "password"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"


class LambdaSanitizer(NodeTransformer):
    """安全检查器，限制只能使用简单 Lambda 表达式"""

    def visit_Name(self, node):
        if node.id == 'x':  # 只允许参数 x
            return node
        raise ValueError(f"Disallowed identifier: {node.id}")

    def visit_Attribute(self, node):
        if isinstance(node.value, Name) and node.value.id == 'x':
            return node  # 允许 x.attribute
        raise ValueError("Disallowed attribute access")


class SSOSession(SQLModel, table=True, table_description="单点登录"):
    __tablename__ = f"{settings.APP_NAME}_sso_session"
    __table_args__ = (
        Index("ix_sso_session_token", "session_token", unique=True),
        Index("ix_sso_refresh_token", "refresh_token", unique=True),
        Index("ix_sso_user_expires", "user_id", "expires_at"),
    )

    # 必需字段
    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    user_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_user.id", title="关联用户ID")  # 必须绑定用户
    session_token: str = Field(..., max_length=1000, title="JWT令牌",
                               sa_column=Column(StringEncryptedType(
                                   type_in=String,
                                   key=settings.SECRET_KEY,
                                   engine=FernetEngine),
                                   unique=True
                               ))
    refresh_token: Optional[str] = Field(None, max_length=1000, title="刷新令牌",
                                         sa_column=Column(StringEncryptedType(
                                             type_in=String,
                                             key=settings.SECRET_KEY,
                                             engine=FernetEngine),
                                             unique=True
                                         ))
    expires_at: datetime = Field(..., title="令牌过期时间")

    # 安全审计字段
    device_fingerprint: str = Field(..., max_length=100, title="设备指纹")
    ip_address: str = Field(..., title="登录IP地址")
    user_agent: str = Field(None, max_length=300, title="客户端标识")

    # 状态管理
    is_active: bool = Field(default=True, title="是否有效会话")
    created_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False),
                                 title="更新时间")

    # 关系定义
    user: "User" = Relationship(back_populates="sso_sessions")

    @staticmethod
    def generate_device_fingerprint(request: Request):
        """
        设备指纹生成方法
        :param request:
        :return: str:
        """
        return sha256(
            f"{request.client.host}-{request.headers.get('user-agent')}".encode()
        ).hexdigest()


class MFASecuity(SQLModel, table=True, table_description="双因素认证表"):
    __tablename__ = f"{settings.APP_NAME}_mfa_secuity"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    user_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_user.id")
    user: "User" = Relationship(back_populates="mfa_methods")
    method_type: str  # "TOTP", "SMS", "Email"
    secret: str  # 加密存储（如TOTP密钥）
    is_active: bool
    last_used: Optional[datetime]


class RevokedToken(SQLModel, table=True, table_description="Token失效表"):
    __tablename__ = f"{settings.APP_NAME}_revoked_token"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    token: str = Field(..., unique=True, index=True)
    revoked_at: datetime = Field(default_factory=datetime.now)
    reason: str = Field("logout", title="撤销原因")


class OauthAccount(SQLModel, table=True, table_description="第三方认证账户表"):
    __tablename__ = f"{settings.APP_NAME}_oauth_account"
    __table_args__ = (UniqueConstraint("user_id", "provider_id", "provider_uid", name="uq_user_account"),
                      )

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    provider_uid: str = Field(..., max_length=100, title="第三方平台用户id")  # 第三方平台用户id
    created_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False),
                                 title="创建时间")
    verification_token: str = Field(..., max_length=500,
                                    sa_column=Column(StringEncryptedType(type_in=String,
                                                                         key=settings.SECRET_KEY,  # 使用配置的密钥
                                                                         engine=FernetEngine  # 使用Fernet加密
                                                                         )))
    access_token: str = Field(..., max_length=500, title="AccessToken",
                              sa_column=Column(StringEncryptedType(type_in=String,
                                                                   key=settings.SECRET_KEY,  # 使用配置的密钥
                                                                   engine=FernetEngine  # 使用Fernet加密
                                                                   )))
    refresh_token: Optional[str] = Field(default="", max_length=500, title="RefreshToken",
                                         sa_column=Column(StringEncryptedType(type_in=String,
                                                                              key=settings.SECRET_KEY,  # 使用配置的密钥
                                                                              engine=FernetEngine  # 使用Fernet加密
                                                                              )))
    expires_at: Optional[datetime] = Field(default_factory=datetime.now,
                                           title="失效时间",
                                           sa_column=Column(
                                               DateTime(timezone=True),
                                               nullable=True
                                           ))

    user_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_user.id", title="UserID")
    user: "User" = Relationship(back_populates="oauth_accounts")
    provider_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_oauth_provider.id", title="ProviderID")
    provider: "OauthProvider" = Relationship(back_populates="oauth_accounts")


class OAuthState(SQLModel, table=True, table_description="Oauth State参数"):
    __tablename__ = f"{settings.APP_NAME}_oauth_state"

    state: str = Field(..., primary_key=True, max_length=50)
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        ),
        title="更新时间"
    )
    redirect_uri: str

    @classmethod
    async def oauth_state_info(cls, session: AsyncSession, redirect_url: str) -> "OAuthState":
        state = generate_random_string(32)
        state_record = cls(
            state=state,
            redirect_uri=redirect_url
        )
        session.add(state_record)
        await session.commit()

        return state_record

    @classmethod
    async def validate_oauth_state(cls, session: AsyncSession, state: str) -> str:
        state_recode = await session.get(cls, state)
        if not state_recode:
            raise ValueError("Invalid state.")

        await session.delete(cls)
        await session.commit()

        if datetime.now() > state_recode.created_at + timedelta(minutes=5):
            raise ValueError("Expired state.")

        return state_recode.redirect_uri


class OauthProviderMixin(SQLModel):
    name: Optional[str] = Field("", max_length=50, nullable=False, unique=True, title="第三方平台名称")
    icon: Optional[str] = Field("", max_length=50, nullable=True, title="第三方图标地址")
    provider_type: ProvideTypeEnum = Field(default=ProvideTypeEnum.Oauth, nullable=False, title="认证方式")
    grant_type: GrantType = Field(default=GrantType.AUTHORIZATION_CODE, nullable=False, title="授权方式")
    client_id: Optional[str] = Field("", max_length=255, nullable=False, title="第三方Client ID")
    client_secret: Optional[str] = Field("", max_length=500, title="Client Secret",
                                         sa_column=Column(StringEncryptedType(type_in=String,
                                                                              key=settings.SECRET_KEY,  # 使用配置的密钥
                                                                              engine=FernetEngine  # 使用Fernet加密
                                                                              ),
                                                          nullable=False, ))
    authorization_url: Optional[str] = Field("", nullable=False, title="授权端点", regex=HTTPS_REGEX)
    token_url: Optional[str] = Field("", title="token端点", regex=HTTPS_REGEX)
    userinfo_url: Optional[str] = Field("", title="用户信息端点", regex=HTTPS_REGEX)
    scope: Optional[str] = Field("", title="默认请求的scope")
    additional_auth_params: Optional[dict] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        title="额外认证参数"
    )
    is_active: Optional[bool] = Field(default=True, sa_column=Column(Boolean, nullable=False), title="是否激活")


class OauthProvider(OauthProviderMixin, table=True, table_description="第三方平台认证表"):
    __tablename__ = f"{settings.APP_NAME}_oauth_provider"
    __table_args__ = (UniqueConstraint("name", "client_id", "client_secret",
                                       name="uq_provider_name_client_credentials"),
                      )

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    config_status: bool = Field(default=False, title="配置是否有效")
    login_count: int = Field(default=0, title="登录有效次数")
    last_success_at: datetime = Field(title="上次登录时间", sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False),
                                 title="更新时间")
    updated_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  onupdate=func.now(),
                                                  nullable=False),
                                 title="更新时间")
    deleted_at: datetime = Field(default=None,
                                 sa_column=Column(DateTime(timezone=True),
                                                  nullable=True),
                                 title="删除时间")

    oauth_accounts: List["OauthAccount"] = Relationship(back_populates="provider")
    field_mappings: List["FieldMapping"] = Relationship(back_populates="provider")

    async def transform_fields(self, raw_data: dict, session: AsyncSession) -> dict:
        field_mappings = {
            data.source_field: (data.target_field, data.transform_rule)
            for data in self.field_mappings
        }

        transformed_data = {}

        transform_audits = []

        for key, value in raw_data.items():
            if key not in field_mappings:
                transformed_data[key] = value
                continue

            target_field, transform_rule = field_mappings[key]

            try:
                if transform_rule.startswith("lambda"):
                    # 语法验证
                    tree = parse(transform_rule, mode='eval')
                    LambdaSanitizer().visit(tree)

                    # 安全执行环境
                    safe_env = {
                        '__builtins__': MappingProxyType({}),
                        'x': value  # 传入当前值作为参数
                    }

                    # 编译并执行
                    compiled = compile(tree, filename='<lambda>', mode='eval')
                    result = eval(compiled, safe_env)

                    transformed_data[target_field] = result
                    transform_audits.append(TransformLog(
                        rule=transform_rule,
                        input_value=value,
                        output_value=result
                    ))
                elif transform_rule == "lowercase":
                    transformed_data[target_field] = value.lower()
                else:
                    transformed_data[target_field] = value
            except Exception as e:
                transform_audits.append(TransformLog(
                    rule=transform_rule,
                    input_value=value,
                    output_value=value,
                    is_error=True,
                    error_msg=str(e)
                ))
                print(e)
                # logger.error(f"Transform failed for {key}: {transform_rule} - {str(e)}")
                transformed_data[target_field] = value  # 保留原始值

        if transform_audits:
            session.add_all(transform_audits)
            await session.commit()

        return transformed_data


class FieldMappingMixin(SQLModel):
    provider_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_oauth_provider.id")
    source_field: str
    target_field: str
    transform_rule: Optional[str]


class FieldMapping(FieldMappingMixin, table=True, table_description="第三方认证回传字段映射表"):
    __tablename__ = f"{settings.APP_NAME}_field_mapping"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    provider: OauthProvider = Relationship(back_populates="field_mappings")
    created_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False),
                                 title="更新时间")
    updated_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  onupdate=func.now(),
                                                  nullable=False),
                                 title="更新时间")
    deleted_at: datetime = Field(default=None,
                                 sa_column=Column(DateTime(timezone=True),
                                                  nullable=True),
                                 title="删除时间")
