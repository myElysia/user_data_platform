from prometheus_client import Counter, Histogram, Gauge, Summary

REQUEST_COUNT = Counter(
    "fastapi_request_count",
    "Total number of requests",
    ["method", "endpoint", "http_status"],
)

REQUEST_LATENCY = Histogram(
    "fastapi_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)

DB_POOL_SIZE = Gauge(
    "db_connection_pool_size",
    "Total connection pool size",
    ["db_type"],
)
DB_ACTIVE_CONNECTIONS = Gauge(
    "db_connection_active",
    "Current active connections",
    ["db_type"],
)
DB_IDLE_CONNECTIONS = Gauge(
    "db_connection_idle",
    "Idle connections in pool",
    ["db_type"],
)

DB_QUERY_COUNTER = Counter(
    "db_query_total",
    "Total database queries",
    ["db_type", "operation"],
)
DB_QUERY_DURATION = Summary(
    "db_query_duration_seconds",
    "Query execution time distribution",
    ["db_type"],
)
DB_ERRORS_COUNTER = Counter(
    "db_errors_total",
    "Database errors count",
    ["db_type", "error_code"],
)
