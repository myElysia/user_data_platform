import os
import uuid
from contextlib import asynccontextmanager

import asyncclick
import uvicorn
from alembic.command import (
    revision as alembic_revision,
    upgrade as alembic_upgrade,
    downgrade as alembic_downgrade
)
from alembic.config import Config
from fastapi import FastAPI, Request, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.cors import CORSMiddleware

from app.interface.api.endpoints import router, oidc_router, admin_router
from app.infrastructure.config.cors import CorsSettings
from app.infrastructure.config.app import AppSettings
from app.infrastructure.database import DatabaseManager, close_metrics
from app.infrastructure.log import AsyncLogger
from app.interface.middlewares.prometheus import register_monitor_middleware
from app.interface.middlewares.rate_limit import register_rate_limit_middleware
from app.interface.middlewares.exception_handler import register_exception_handlers
from app.interface.middlewares.security_headers import register_security_headers
from app.infrastructure.utils.healthcheck import HealthCheck

app_settings = AppSettings()
cors_settings = CorsSettings()
database_manager = DatabaseManager()
logger = AsyncLogger.get_logger(**{"name": __name__})

# 获取当前文件的绝对路径
ABS_PATH = os.path.dirname(os.path.abspath(__file__))
# 设置正确的 migrations 路径
migrations_path = os.path.join(ABS_PATH, "migrations")
alembic_config = Config()
alembic_config.set_main_option("script_location", migrations_path)
alembic_config.set_main_option("sqlalchemy.url", database_manager._settings.db_url)
alembic_config.set_main_option("file_template", "%%(year)d%%(month).2d%%(day).2d_%%(rev)s-%%(slug)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # 进行健康检查,防止数据库或者Redis在运行前出现问题
        await HealthCheck.run_all()
        yield
    except Exception as e:
        await logger.error(e)
        raise e
    finally:
        await database_manager.close_all()
        # 清理指标监控
        close_metrics()


app = FastAPI(
    lifespan=lifespan,
    title="Zero Trust OIDC Platform",
    description="零信任 OIDC 用户中台 — 类 GitHub OAuth Apps 的系统接入能力",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    **cors_settings.cors_config,
)
register_monitor_middleware(app)
register_rate_limit_middleware(app)
register_exception_handlers(app)
register_security_headers(app)
app.include_router(router)
app.include_router(oidc_router)
app.include_router(admin_router)


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
    request.state.request_id = unique_id
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


@cli.command("worker")
@asyncclick.option("--max-jobs", default=10, type=int, help="并发任务数")
async def start_worker(max_jobs: int):
    """启动 ARQ 后台任务 worker（生产模式，需要 Redis；不可用时请直接运行 start，任务将进程内降级执行）"""
    import arq
    from app.infrastructure.messaging.worker import build_worker_settings

    settings = build_worker_settings()
    settings["max_jobs"] = max_jobs
    worker = arq.Worker(**settings)
    try:
        asyncclick.echo(f"ARQ worker 启动中 (Redis {settings['redis_settings'].host}:{settings['redis_settings'].port})...")
        await worker.async_run()
    except Exception as e:
        asyncclick.echo(f"ARQ worker 启动失败（Redis 不可用？）: {e}")
        ctx = asyncclick.get_current_context()
        ctx.exit(1)


# 修改3：将db_cli注册为cli的子组
@cli.group("db", invoke_without_command=True)
@asyncclick.pass_context
async def db_cli(ctx):
    """数据库迁移命令组"""
    if ctx.invoked_subcommand is None:
        asyncclick.echo(ctx.get_help())
        ctx.exit()


@db_cli.command()  # ignore 实际可以执行
@asyncclick.option("--message", "-m", default=f"auto-revision-name", type=str)
async def revision(message: str):
    """创建迁移版本,  --manager -m: 迁移备注"""
    # 强制导入模型以确保元数据加载
    import asyncio
    await asyncio.to_thread(alembic_revision, alembic_config, message, autogenerate=True)


@db_cli.command()  # ignore 实际可以执行
@asyncclick.option("--version", "-v", default="heads", type=str)
async def migrate(version: str):
    """应用迁移, --version -v: 迁移的版本"""
    import asyncio
    await asyncio.to_thread(alembic_upgrade, alembic_config, version)


@db_cli.command()  # ignore 实际可以执行
@asyncclick.option("--steps", type=int, default=1, help="回滚步数")
async def downgrade(steps):
    """回滚迁移, --steps 回滚步数,默认1"""
    import asyncio
    await asyncio.to_thread(alembic_downgrade, alembic_config, f"-{steps}")


if __name__ == '__main__':
    cli(_anyio_backend="asyncio")
