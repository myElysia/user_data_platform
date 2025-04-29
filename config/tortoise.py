from typing import Dict, Any
from pydantic import field_validator

from . import EnvSettings


class Settings(EnvSettings):
    DB_ENGINE: str = ''
    DB_USER: str = ''
    DB_PASS: str = ''
    DB_HOST: str = ''
    DB_PORT: int = 5432
    DB_NAME: str = ''
    MIN_CONNECT: int = 3
    MAX_CONNECT: int = 20
    CONN_TIMEOUT: int = 30
    CONN_LIFETIME: int = 300

    class Config:
        env_file = ".env"
        extra = "ignore"  # 忽略多余的环境变量

    # 校验是否存在数据库连接地址
    @field_validator("DB_HOST")
    def validate_db_host(cls, v):
        if not v:
            raise ValueError("DB_HOST")
        return v

    @property
    def tortoise_config(self) -> dict:
        return {
            "connections": self.connection_pool_kw,
            "apps": self.apps_kw
        }

    @property
    def connection_pool_kw(self) -> Dict[str, Any]:
        return {
            "default": {
                "engine": self.DB_ENGINE,
                "credentials": {
                    "database": self.DB_NAME,
                    "host": self.DB_HOST,
                    "port": self.DB_PORT,
                    "user": self.DB_USER,
                    "password": self.DB_PASS,  # Tortoise使用config的情况下会自动处理密码(quote_plus)
                    "minsize": self.MIN_CONNECT,  # 最小连接数
                    "maxsize": self.MAX_CONNECT,  # 最大连接数
                    "command_timeout": self.CONN_TIMEOUT,  # 查询超时(秒)
                    "max_inactive_connection_lifetime": self.CONN_LIFETIME,  # 空闲连接存活时间
                }
            }
        }

    @property
    def apps_kw(self) -> Dict[str, Any]:
        return {
            "models": {
                "models": ["app.db.models", "aerich.models"],
                "default_connection": "default",
            }
        }


try:
    settings = Settings()
except Exception as e:
    print(e)
    import sys

    sys.exit(1)
