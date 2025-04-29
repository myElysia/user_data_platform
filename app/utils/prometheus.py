import asyncio

from app.utils.database import get_connection
from config.prometheus import DB_POOL_SIZE


async def monitor_db_pool():
    while True:
        await asyncio.sleep(300)
        conn = get_connection()
        if hasattr(conn, 'pool'):
            DB_POOL_SIZE.labels('active').set(conn.pool.get_active_connections())
            DB_POOL_SIZE.labels('idle').set(conn.pool.get_idle_connections())
