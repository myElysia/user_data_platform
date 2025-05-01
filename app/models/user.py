from tortoise import fields

from app.models.base import WithTimeBase, Base


class User(WithTimeBase):
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=100, unique=True)
    phone = fields.CharField(max_length=20, null=True)
    display_name = fields.CharField(max_length=255)
    hashed_password = fields.CharField(max_length=255, null=True)
    is_active = fields.BooleanField(default=True)
    is_superuser = fields.BooleanField(default=False)

    def __str__(self):
        return self.username

    class Meta:
        table = "user_user"

    def to_dict(self, use_password=False):
        data = {i: getattr(self, i) for i in self.__dict__ if not i.startswith('_')}
        if not use_password:
            del data['password']
        return data

    async def has_permission(self, permission_code: str) -> bool:
        if self.is_superuser:
            return True
        return bool(UserRole
                    .filter(user=self)
                    .filter(role__role_permissions__permission__code=permission_code)
                    .exists())

    async def get_roles(self) -> list[str]:
        # 获取用户所有角色名称
        roles = await UserRole.filter(user=self).prefetch_related("role")
        return [role.role.name for role in roles]


class ThirdPartyProvider(Base):
    name = fields.CharField(max_length=255)
    icon = fields.CharField(max_length=255, null=True)
    provider_type = fields.CharField(max_length=20)  # oauth2/saml/oidc
    client_id = fields.CharField(max_length=255)
    client_secret = fields.CharField(max_length=255)
    authorization_url = fields.TextField(null=True)  # 授权端点
    token_url = fields.TextField(null=True)  # token端点
    userinfo_url = fields.TextField(null=True)  # 用户信息端点
    scope = fields.TextField(null=True)  # 默认请求的scope
    additional_auth_params = fields.JSONField(null=True)  # 额外的认证参数
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "third_party_provider"

    def __str__(self):
        return self.name


class ThirdPartyAccount(WithTimeBase):
    user = fields.ForeignKeyField("models.User", related_name="third_party_accounts")
    provider = fields.ForeignKeyField("models.ThirdPartyProvider", related_name="third_party_accounts")
    provider_uid = fields.CharField(max_length=50)  # 第三方平台用户id
    access_token = fields.CharField(max_length=255)
    refresh_token = fields.CharField(max_length=255)
    expires_at = fields.DatetimeField(null=True)

    class Meta:
        table = "third_party_account"
        unique_together = ("provider_id", "provider_uid")


class Role(Base):
    name = fields.CharField(max_length=50, unique=True)
    description = fields.CharField(max_length=255)

    class Meta:
        table = "user_role"


class Permission(Base):
    code = fields.CharField(max_length=50, unique=True)
    description = fields.CharField(max_length=255)

    class Meta:
        table = "user_permission"


class RolePermission(Base):
    role = fields.ForeignKeyField("models.Role", on_delete=fields.CASCADE, related_name="permissions")
    permission = fields.ForeignKeyField("models.Permission", on_delete=fields.CASCADE, related_name="roles")

    class Meta:
        table = "user_role_permission"
        unique_together = ("role_id", "permission_id")


class UserRole(Base):
    user = fields.ForeignKeyField("models.User", on_delete=fields.CASCADE, related_name="roles")
    role = fields.ForeignKeyField("models.Role", on_delete=fields.CASCADE, related_name="users")

    class Meta:
        table = "user_user_role"
        unique_together = ("user_id", "role_id")
