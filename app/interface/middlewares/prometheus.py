import time

from fastapi import FastAPI

from app.infrastructure.prometheus import REQUEST_COUNT, REQUEST_LATENCY


def register_monitor_middleware(app: FastAPI):
    """注册 Prometheus 监控中间件到 FastAPI 应用"""

    @app.middleware("http")
    async def monitor_requests(request, call_next):
        method = request.method
        endpoint = request.url.path

        start_time = time.time()
        response = await call_next(request)
        latency = time.time() - start_time

        REQUEST_COUNT.labels(method, endpoint, response.status_code).inc()
        REQUEST_LATENCY.labels(method, endpoint).observe(latency)

        return response
