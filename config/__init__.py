from abc import ABC, abstractmethod
from pydantic_settings import BaseSettings


class EnvSettings(BaseSettings, ABC):
    class Config:
        env_file = ".env"
        extra = 'ignore'
