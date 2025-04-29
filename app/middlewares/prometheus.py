import time

from config.prometheus import REQUEST_COUNT, REQUEST_LATENCY
from main import app


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
