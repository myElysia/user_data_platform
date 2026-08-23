from functools import cached_property
from typing import Dict, Any

from app.infrastructure.config.base import EnvSettings


class CorsSettings(EnvSettings):
    ALLOW_ORIGINS: list[str] = ["*"]
    ALLOW_METHODS: list[str] = ["*"]
    ALLOW_HEADERS: list[str] = ["*"]
    ALLOW_CREDENTIALS: bool = True
    EXPOSE_HEADERS: list[str] = ["*"]
    MAX_AGE: int = 600

    @cached_property
    def prefix(self):
        return ""

    @property
    def cors_config(self) -> Dict[str, Any]:
        return {
            "allow_origins": self.ALLOW_ORIGINS,
            "allow_methods": self.ALLOW_METHODS,
            "allow_headers": self.ALLOW_HEADERS,
            "allow_credentials": self.ALLOW_CREDENTIALS,
            "expose_headers": self.EXPOSE_HEADERS,
            "max_age": self.MAX_AGE,
        }
