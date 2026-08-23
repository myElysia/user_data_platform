import json
from functools import wraps
from http import HTTPStatus
from typing import TypeVar, Generic, List, Self, Dict, Any, Type

from pydantic import BaseModel
from starlette.requests import Request

_MODEL = TypeVar("_MODEL", bound=BaseModel)


def request_hook(model: Type[BaseModel]):
    """
    封装参数返回值,避免反复手动实现Response
    :param model:
    :return:
    """

    def response_maker(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            from app.infrastructure.log import AsyncLogger

            context = dict(
                request_id=request.state.request_id,
                request_method=request.method,
                route=request.scope.get("path"),
                remote_ip=request.scope.get("client")[0],
            )
            try:
                data = await func(request, *args, **kwargs)

                context.update({"data": json.dumps(data)})
                logger = AsyncLogger.get_logger(**context)
                logger.info("OK.")

                return Response[model](data=data)
            except Exception as e:
                logger = AsyncLogger.get_logger(**context)
                logger.error(e)

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
        """
        错误类型注解
        :param error:
        :param code:
        :return:
        """
        if isinstance(error, Exception):
            error = str(error)
        return cls[dict](code=code, message="FAIL", data={"error": error})


__all__ = ["request_hook"]
