"""全局异常处理器 — 统一错误响应格式"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from app.infrastructure.log import AsyncLogger

_logger = AsyncLogger.get_logger(**{"name": "exception_handler"})


def register_exception_handlers(app):
    """注册全局异常处理器到 FastAPI 应用"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        await _logger.warning(
            f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}",
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                "code": exc.status_code,
                "path": request.url.path,
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        await _logger.warning(
            f"Validation error on {request.method} {request.url.path}: {exc.errors()}",
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation failed",
                "code": 422,
                "path": request.url.path,
                "details": exc.errors(),
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        await _logger.warning(
            f"ValueError on {request.method} {request.url.path}: {exc}",
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": str(exc),
                "code": 400,
                "path": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        await _logger.error(
            f"Unhandled error [{request_id}] on {request.method} {request.url.path}: {exc}",
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "code": 500,
                "path": request.url.path,
                "request_id": request_id,
            },
        )