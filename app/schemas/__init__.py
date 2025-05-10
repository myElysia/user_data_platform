from pydantic import BaseModel


class BaseModelConfig(BaseModel):
    class Config:
        from_attributes = True  # Pydantic v2 新语法, 允许转换orm
