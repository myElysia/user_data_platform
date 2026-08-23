from functools import cached_property

from app.infrastructure.config.base import EnvSettings


class AppSettings(EnvSettings):
    APP_NAME: str = ""
    VERSION: str = ""
    SECRET_KEY: str = ""
    ALGORITHM: str = ""

    @cached_property
    def prefix(self):
        return ""
