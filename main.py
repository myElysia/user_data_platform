import contextvars
import uuid
from contextlib import asynccontextmanager

import asyncclick
import uvicorn
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


@asyncclick.group("app", invoke_without_command=True)  # 修改1：主命令组命名为"app"
@asyncclick.pass_context
async def cli(ctx):
    """主命令行组"""
    if ctx.invoked_subcommand is None:
        # 如果没有子命令，显示帮助信息
        asyncclick.echo(ctx.get_help())
        ctx.exit()


@cli.command("start")  # 修改2：将start作为子命令
@asyncclick.option("--host", default="0.0.0.0", help="监听主机")
@asyncclick.option("--port", default=8000, type=int, help="监听端口")
@asyncclick.option("--reload", is_flag=True, default=True, help="启用热重载")
@asyncclick.option("--log-level", default="info", help="日志级别")
async def start_server(host, port, reload, log_level):
    """启动服务器"""
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        reload_delay=5,
        log_level=log_level
    )


# 修改3：将db_cli注册为cli的子组
@cli.group("db", invoke_without_command=True)
@asyncclick.pass_context
async def db_cli(ctx):
    """数据库迁移命令组"""
    if ctx.invoked_subcommand is None:
        asyncclick.echo(ctx.get_help())
        ctx.exit()


@db_cli.command()  # ignore 实际可以执行
@asyncclick.argument("name", default="migrations", type=str)
async def init(name):
    """初始化迁移文件"""
    print(f"初始化迁移文件成功: {name}")


@db_cli.command()  # ignore 实际可以执行
@asyncclick.option("--manager", "-m", default=f"auto-revision-name", type=str)
async def revision(manager):
    """创建迁移版本,  --manager -m: 迁移备注"""
    print(f"{manager}")


@db_cli.command()  # ignore 实际可以执行
async def migrate():
    """应用迁移"""
    ...


@db_cli.command()  # ignore 实际可以执行
@asyncclick.option("--steps", type=int, default=1, help="回滚步数")
async def downgrade(steps):
    """回滚迁移, --steps 回滚步数,默认1"""
    steps = -1 * steps
    print(f"回滚 {steps} 个迁移")


if __name__ == '__main__':
    cli(_anyio_backend="asyncio")
