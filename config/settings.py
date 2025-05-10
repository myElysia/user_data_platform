from . import EnvSettings


class Settings(EnvSettings):
    VERSION: str
    SECRET_KEY: str
    ALGORITHM: str
