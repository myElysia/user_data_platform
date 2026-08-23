from abc import ABC, abstractmethod
from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings, ABC):
    """
    通过 .env 文件配置的环境参数获取变量。
    变量方法为 items(), 自动忽略前缀 prefix 中的字符串。
    注意：子类自动单例，重复调用返回同一实例。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @abstractmethod
    @cached_property
    def prefix(self):
        raise NotImplementedError

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, **data):
        # 单例模式：仅首次调用时执行 pydantic 初始化
        if hasattr(self, "_initialized"):
            return
        super().__init__(**data)
        self._initialized = True

    @property
    def items(self) -> dict[str, str]:
        return {k[len(self.prefix):].lower(): v for k, v in self.model_dump().items()}
