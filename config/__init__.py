from abc import ABC, abstractmethod
from pydantic_settings import BaseSettings


class EnvSettings(BaseSettings, ABC):
    class Config:
        env_file = ".env"
        extra = 'ignore'

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance
