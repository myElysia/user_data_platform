from tortoise import Tortoise, BaseDBAsyncClient

def get_connection() -> BaseDBAsyncClient:
    """
    获取连接池
    active: conn.pool.get_active_connections()
    idle: conn.pool.get_idle_connections()
    :return:
    """
    conn = Tortoise.get_connection("default")
    return conn
