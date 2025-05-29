import contextvars
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.cors import CORSMiddleware

from app.api.endpoints import router
from app.local.cors import Settings as Cors_settings
from app.local.database import Settings as Database_settings, close_metrics
from app.local.settings import Settings
from app.utils.healthcheck import HealthCheck

settings = Settings()
cors_settings = Cors_settings()
database_settings = Database_settings()

# 全局上下文对象，用于存储 request_id
request_id = contextvars.ContextVar(settings.APP_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # 进行健康检查,防止数据库或者Redis崩溃
        await HealthCheck.run_all()

        yield
    except Exception as e:
        print(f"Lifespan error: {e}")
        raise e
    finally:
        await database_settings.close_all()
        # 清理指标监控
        close_metrics()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    **cors_settings.cors_config,
)
app.include_router(router)


@app.middleware("http")
async def request_id_wrapper(request: Request, call_next) -> Response:
    """
    Http中间件，用以在每个请求处理前生成一个唯一的request_id，存储于上下文中
    :param request: FastApi请求对象，包含客户端请求信息
    :param call_next: (Callable) 用来调用下一个请求处理程序的回调函数，接受 Request 对象并返回 Response 对象
    :return: 处理后的 Http响应对象
    """
    # 生成 UUID
    unique_id = str(uuid.uuid4())
    request_id.set(unique_id)
    # 继续处理请求并返回响应
    response = await call_next(request)
    # 往响应中加入 request_id
    response.headers["X-Request-Id"] = unique_id
    return response


@app.get("/metrics")
async def metrics():
    """
    Prometheus 监控端点
    :return:
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/healthy")
async def health():
    """
    Healthcheck
    :return:
    """
    from http import HTTPStatus

    return {"code": HTTPStatus.OK, "message": "running"}
