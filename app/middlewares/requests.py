import uuid
from fastapi import (
    Request,
    Response
)

from main import (
    app,
    request_id
)


@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:
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

