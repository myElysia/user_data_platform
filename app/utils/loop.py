from functools import wraps, partial


def async_func(func):
    """
    通过注入loop实现在同步代码中可以运行异步代码
    :param func:
    :return:
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop_func = partial(loop.run_until_complete)
        try:
            func(*args, **kwargs, async_runner=loop_func)
        finally:
            loop.close()
    return wrapper
