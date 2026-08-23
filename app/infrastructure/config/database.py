from functools import cached_property
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_core.core_schema import ValidationInfo

from app.infrastructure.config.base import EnvSettings

# 支持的数据库引擎
SUPPORTED_ENGINES = ("sqlite+aiosqlite", "postgresql+asyncpg", "mysql+asyncmy")


class DatabaseSettings(EnvSettings):
    APP_NAME: str = ""
    DB_ENGINE: str = "sqlite+aiosqlite"
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_HOST: str = ""
    DB_PORT: int = 5432
    DB_DATABASE: str = "user_platform.db"
    DB_MINSIZE: int = 3
    DB_MAXSIZE: int = 20
    DB_COMMAND_TIMEOUT: int = 30
    DB_MAX_INACTIVE_CONNECTION_LIFETIME: int = 300  # 单位：秒

    @cached_property
    def prefix(self):
        return "DB_"

    @field_validator("DB_ENGINE")
    def validate_engine(cls, v):
        if v not in SUPPORTED_ENGINES:
            raise ValueError(
                f"DB_ENGINE must be one of {SUPPORTED_ENGINES}, got {v}"
            )
        return v

    @field_validator("DB_MAXSIZE")
    def validate_pool_size(cls, v, info: ValidationInfo):
        if v <= info.data["DB_MINSIZE"]:
            raise ValueError("DB_MAXSIZE must be greater than DB_MINSIZE")
        return v

    @property
    def is_sqlite(self) -> bool:
        """是否使用 SQLite（单文件模式）"""
        return self.DB_ENGINE.startswith("sqlite")

    @property
    def is_mysql(self) -> bool:
        return self.DB_ENGINE.startswith("mysql")

    @property
    def _password(self):
        return quote_plus(self.DB_PASSWORD)

    @property
    def db_url(self) -> str:
        """构建数据库 URL — 按引擎分支

        - sqlite+aiosqlite:///./user_platform.db（本地文件，无需认证）
        - postgresql+asyncpg://user:pass@host:port/database
        - mysql+asyncmy://user:pass@host:port/database
        """
        if self.is_sqlite:
            return f"sqlite+aiosqlite:///./{self.DB_DATABASE}"
        return (
            f"{self.DB_ENGINE}://{self.DB_USER}:{self._password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"
        )
