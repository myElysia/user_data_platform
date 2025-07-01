from functools import wraps
from http import HTTPStatus
from typing import TypeVar, Generic, List, Self, Dict, Any, Type

from pydantic import BaseModel

_MODEL = TypeVar("_MODEL", bound=BaseModel)


def response_handler(model: Type[BaseModel]):
    """
    封装参数返回值,避免反复手动实现Response
    :param model:
    :return:
    """

    def response_maker(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return Response[model](data=await func(*args, **kwargs))
            except Exception as e:
                return Response.on_error(e)

        return wrapper

    return response_maker


class Response(BaseModel, Generic[_MODEL]):
    code: int | None = HTTPStatus.OK
    message: str | None = "SUCCESS"
    data: _MODEL | List[_MODEL] | Dict[str, Any] = None

    @classmethod
    def on_error(cls,
                 error: Exception | str,
                 code: int = HTTPStatus.INTERNAL_SERVER_ERROR) -> "Self":
        if isinstance(error, Exception):
            error = str(error)
        return cls(code=code, message="FAIL", data={"error": error})


__all__ = ["response_handler"]
