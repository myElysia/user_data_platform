from http import HTTPStatus
from typing import TypeVar, Generic, List, Self, Dict

from pydantic import BaseModel

_MODEL = TypeVar("_MODEL", bound=BaseModel)


class Response(BaseModel, Generic[_MODEL]):
    code: int | None = HTTPStatus.OK
    message: str | None = "SUCCESS"
    data: _MODEL | List[_MODEL] | Dict[str, any] = None

    @classmethod
    def on_error(cls,
                 error: Exception | str,
                 code: int = HTTPStatus.INTERNAL_SERVER_ERROR) -> "Self":
        if isinstance(error, Exception):
            error = error.__str__()
        return cls(code=code, message="FAIL", data={"error": error})


__all__ = ["Response"]
