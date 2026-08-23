from functools import cached_property
from typing import Dict, Any

from pydantic import field_validator

from app.infrastructure.config.base import EnvSettings


class RedisSettings(EnvSettings):
    REDIS_HOST: str = ""
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 20
    REDIS_DECODE_RESPONSES: bool = True

    @field_validator("REDIS_HOST")
    def validate_host(cls, v):
        if v == "":
            raise ValueError("REDIS_HOST cannot be empty")
        return v

    @cached_property
    def prefix(self):
        return "REDIS_"

    @property
    def connection_pool_kw(self) -> Dict[str, Any]:
        return {
            "host": self.REDIS_HOST,
            "port": self.REDIS_PORT,
            "db": self.REDIS_DB,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "password": self.REDIS_PASSWORD,
            "decode_responses": self.REDIS_DECODE_RESPONSES,
        }
