from functools import wraps


def async_lock_hook(func):
    """
    协程锁
    :param func:
    :return:
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        from asyncio import Lock

        lock: Lock = Lock()
        async with lock:
            return await func(*args, **kwargs)

    return wrapper
