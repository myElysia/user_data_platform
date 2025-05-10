from typing import Dict, Any

from . import EnvSettings


class Settings(EnvSettings):
    ALLOW_ORIGINS: list[str] = ["*"]  # 允许所有来源
    ALLOW_METHODS: list[str] = ["*"]  # 允许所有 HTTP 方法
    ALLOW_HEADERS: list[str] = ["*"]  # 允许所有请求头（可选）
    ALLOW_CREDENTIALS: bool = True  # 允许携带凭据（如 cookies，可选）
    EXPOSE_HEADERS: list[str] = ["*"]  # 允许浏览器访问的响应头（可选）
    MAX_AGE: int = 600  # 预检请求缓存时间（可选）

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
