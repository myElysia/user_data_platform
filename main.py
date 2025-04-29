import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from tortoise import Tortoise

from app.middlewares.database import DBCleanupMiddleWare
from app.utils.prometheus import monitor_db_pool
from app.utils.healthcheck import HealthCheck
from config.cors import Settings as Cors_settings
from config.tortoise import Settings as Tortoise_settings

cors_settings = Cors_settings()
tortoise_settings = Tortoise_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await Tortoise.init(config=tortoise_settings.tortoise_config)

        # 进行健康检查,防止数据库或者Redis崩溃
        await HealthCheck.run_all()

        asyncio.create_task(monitor_db_pool())

        yield
    except Exception as e:
        print(f"Lifespan error: {e}")
        raise e
    finally:
        await Tortoise.close_connections()
    # logger.info("Database connections closed gracefully")


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    **cors_settings.cors_config,
)
app.add_middleware(DBCleanupMiddleWare)
