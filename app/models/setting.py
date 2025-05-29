from sqlalchemy import Integer, Column
from sqlmodel import SQLModel, Field

from app.local.settings import Settings

settings = Settings()


class SecurityPolicy(SQLModel, table=True, table_description="安全配置策略"):
    __tablename__ = f"{settings.APP_NAME}_security_policy"

    id: int = Field(..., sa_column=Column(Integer, autoincrement=True, primary_key=True), allow_mutation=False)
    password_min_length: int = Field(8, title="密码最小长度")
    allow_common_password: bool = Field(False, title="允许常见弱密码")
