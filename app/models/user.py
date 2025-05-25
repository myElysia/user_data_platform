from ast import parse, NodeTransformer, Name
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
from types import MappingProxyType
from typing import Optional, List

from sqlalchemy import Column, Boolean, DateTime, UniqueConstraint, JSON, String, Index, Integer, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_utils import StringEncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import FernetEngine
from sqlmodel import Field, Relationship, SQLModel
from starlette.requests import Request

from app.local.settings import Settings
from app.utils.security import generate_random_string

settings = Settings()
HTTPS_REGEX = r"^https?://.+"


class UserRole(str, Enum):
    ADMIN = "admin"
    GUEST = "guest"
    USER = "user"


class UserMixin(SQLModel):
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None
    hash_password: Optional[str] = None
    # 用户权限, 只有admin/guest 支持访问后台
    role: UserRole = Field(UserRole.USER)


class User(UserMixin, table=True, table_description="用户表"):
    __tablename__ = f"{settings.APP_NAME}_user"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    username: Optional[str] = Field("", max_length=50, nullable=False, unique=True, title="用户名")
    email: Optional[str] = Field("", max_length=255, nullable=False, unique=True, title="邮箱")
    country: Optional[str] = Field("China", max_length=100, nullable=False, title="国家")
    language: Optional[str] = Field("zh-CN", nullable=False, title="语言配置")
    phone: Optional[str] = Field("", max_length=255, nullable=True, unique=True, title="电话")
    display_name: Optional[str] = Field("", max_length=50, nullable=True, title="个人昵称")
    hash_password: str = Field("", max_length=255, nullable=False, title="密码")
    is_active: bool = Field(True, sa_column=Column(Boolean, nullable=False), title="是否激活")
    created_at: datetime = Field(default_factory=datetime.now,
                                 sa_column=Column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  nullable=False),
                                 title="创建时间")
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
    # 用户验证相关
    email_verified: bool = False
    phone_verified: bool = False
    # 以下是外键列表
    accounts: List["ThirdPartyAccount"] = Relationship(back_populates="user")
    verifications: List["UserVerification"] = Relationship(back_populates="user")
    sso_sessions: List["SSOSession"] = Relationship(back_populates="user")
    audit_logs: List["AuditLog"] = Relationship(back_populates="user")
    # 以下是用户多对多关系列表

    # 去除密码字段,仅在模型中可读写
    model_config = {
        "exclude": ["password"]
    }


class VerificationType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"


class UserVerification(SQLModel, table=True, table_description="邮箱验证码"):
    __tablename__ = f"{settings.APP_NAME}_user_verification"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    user: User = Relationship(back_populates="verifications")
    user_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_user.id", title="关联用户ID")  # 必须绑定用户
    verify_type: VerificationType = Field(VerificationType.EMAIL)
    code: str = Field(..., max_length=500, title="验证码",
                      sa_column=Column(StringEncryptedType(
                          type_in=String,
                          key=settings.SECRET_KEY,
                          engine=FernetEngine),
                          unique=True
                      ))
    attempts: int = Field(0, title="尝试次数")


class SecurityPolicy(SQLModel, table=True, table_description="安全配置策略"):
    __tablename__ = f"{settings.APP_NAME}_security_policy"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    password_min_length: int = Field(8, title="密码最小长度")
    allow_common_password: bool = Field(False, title="允许常见弱密码")


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
    user: User = Relationship(back_populates="sso_sessions")

    @staticmethod
    def generate_device_fingerprint(request: Request):
        return sha256(
            f"{request.client.host}-{request.headers.get('user-agent')}".encode()
        ).hexdigest()


class RevokedToken(SQLModel, table=True, table_description="Token失效表"):
    __tablename__ = f"{settings.APP_NAME}_revoked_token"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    token: str = Field(..., unique=True, index=True)
    revoked_at: datetime = Field(default_factory=datetime.now)
    reason: str = Field("logout", title="撤销原因")


class ProvideTypeEnum(str, Enum):
    # 认证方式
    Oauth = "oauth"
    Saml = "saml"
    Oidc = "oidc"


class GrantType(str, Enum):
    # 授权方式
    CODE = "authorization_code"
    IMPLICIT = "implicit"
    PASSWORD = "password"


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


class ThirdPartyProviderMixin(SQLModel):
    name: Optional[str] = Field("", max_length=50, nullable=False, unique=True, title="第三方平台名称")
    icon: Optional[str] = Field("", max_length=50, nullable=True, title="第三方图标地址")
    provider_type: ProvideTypeEnum = Field(default=ProvideTypeEnum.Oauth, nullable=False, title="认证方式")
    grant_type: GrantType = Field(default=GrantType.CODE, nullable=False, title="授权方式")
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
    field_mappings: Optional[dict]


class ThirdPartyProvider(ThirdPartyProviderMixin, table=True, table_description="第三方平台认证表"):
    __tablename__ = f"{settings.APP_NAME}_third_party_provider"
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

    accounts: List["ThirdPartyAccount"] = Relationship(back_populates="provider")
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
    provider_id: int = Field(..., foreign_key=f"{settings.APP_NAME}_third_party_provider.id")
    source_field: str
    target_field: str
    transform_rule: Optional[str]


class FieldMapping(FieldMappingMixin, table=True, table_description="第三方认证回传字段映射表"):
    __tablename__ = f"{settings.APP_NAME}_field_mapping"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    provider: ThirdPartyProvider = Relationship(back_populates="field_mappings")
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


class ThirdPartyAccount(SQLModel, table=True, table_description="第三方认证账户表"):
    __tablename__ = f"{settings.APP_NAME}_third_party_account"
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

    user_id: int = Field(default=None, foreign_key=f"{settings.APP_NAME}_user.id", title="UserID")
    user: "User" = Relationship(back_populates="third_party_accounts")
    provider_id: int = Field(default=None, foreign_key=f"{settings.APP_NAME}_third_party_provider.id",
                             title="ProviderID")
    provider: "ThirdPartyProvider" = Relationship(back_populates="third_party_accounts")


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
    user_id: Optional[int] = Field(..., foreign_key=f"{settings.APP_NAME}_user.id")
    action: str
    ip_address: str
    target_resource_id: Optional[int]  # 操作的目标资源ID（如被修改的用户ID）
    request_metadata: dict = Field(sa_column=Column(JSON))  # 请求头、UA、设备信息
    operation_type: str  # CREATE/UPDATE/DELETE等
    old_value: Optional[str]  # 修改前的值（如角色变更前）
    new_value: Optional[str]  # 修改后的值
