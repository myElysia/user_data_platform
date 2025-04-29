from prometheus_client import Counter, Histogram, Gauge

# 请求数
REQUEST_COUNT = Counter(
    'fastapi_request_count',
    'Total number of requests',
    ['method', 'endpoint', 'http_status']
)

REQUEST_LATENCY = Histogram(
    'fastapi_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint']
)

# 连接池指标
DB_POOL_SIZE = Gauge(
    'db_pool_size',
    'Current database connection pool size',
    ['state']  # active/idle
)
