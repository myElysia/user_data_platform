from functools import cached_property

from . import EnvSettings


class Settings(EnvSettings):
    APP_NAME: str = ""
    VERSION: str = ""
    SECRET_KEY: str = ""
    ALGORITHM: str = ""

    @cached_property
    def prefix(self):
        return ""
