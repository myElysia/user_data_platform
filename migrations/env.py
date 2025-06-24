from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from app.local.database import Settings
from app.models import METADATA

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
async_sessionmaker = Settings()

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = METADATA


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


async def async_run_migrations_online() -> None:
    # 从 Settings 实例获取异步引擎
    engine = async_sessionmaker.async_engine

    # 使用异步引擎执行迁移
    async with engine.begin() as connection:
        # 将异步连接转换为同步上下文所需的连接
        sync_connection = await connection.get_raw_connection()

        print(sync_connection)
        # 配置 Alembic 上下文
        context.configure(
            connection=sync_connection.driver_connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        # 在事务中运行迁移
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    print("test")
    asyncio.run(async_run_migrations_online())
