"""限流中间件 — 滑动窗口限流，基于 CacheBackend（Redis 可用走 Redis，否则降级内存）"""

import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, HTTPException
from starlette.responses import Response

from app.infrastructure.cache import get_cache_backend


class RateLimiter:
    """滑动窗口限流器（CacheBackend 接口）"""

    def __init__(
        self,
        window_seconds: int = 60,
        max_requests: int = 100,
        key_prefix: str = "rate_limit",
    ):
        self.window = window_seconds
        self.max_requests = max_requests
        self.key_prefix = key_prefix

    def _build_key(self, identifier: str) -> str:
        return f"{self.key_prefix}:{identifier}"

    async def is_allowed(self, identifier: str) -> tuple[bool, int, int]:
        """检查是否允许请求

        Returns:
            (allowed, remaining, reset_in_seconds)
        """
        key = self._build_key(identifier)
        now = time.time()
        window_start = now - self.window

        backend = await get_cache_backend()
        # 移除窗口外的记录
        await backend.zremrangebyscore(key, 0, window_start)
        # 统计当前窗口内的请求数
        current_count = await backend.zcard(key)
        # 添加当前请求（成员名必须唯一：纳秒时间戳+随机后缀，避免高频请求覆盖）
        await backend.zadd(key, {f"{time.time_ns()}:{uuid.uuid4().hex[:12]}": now})

        remaining = max(0, self.max_requests - current_count)
        reset_in = int(self.window - (now - window_start))

        return current_count < self.max_requests, remaining, reset_in

    async def get_usage(self, identifier: str) -> dict:
        """获取使用统计"""
        key = self._build_key(identifier)
        now = time.time()
        window_start = now - self.window

        backend = await get_cache_backend()
        await backend.zremrangebyscore(key, 0, window_start)
        count = await backend.zcard(key)
        return {
            "identifier": identifier,
            "current_usage": count,
            "limit": self.max_requests,
            "window_seconds": self.window,
            "remaining": max(0, self.max_requests - count),
        }


# 预定义限流策略
client_rate_limiter = RateLimiter(
    window_seconds=60, max_requests=100, key_prefix="rate_limit_client",
)

user_rate_limiter = RateLimiter(
    window_seconds=60, max_requests=200, key_prefix="rate_limit_user",
)

token_endpoint_limiter = RateLimiter(
    window_seconds=60, max_requests=30, key_prefix="rate_limit_token",
)


def register_rate_limit_middleware(app: FastAPI):
    """注册限流中间件"""

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
        # 跳过健康检查和 metrics 端点
        path = request.url.path
        if path in ("/healthy", "/metrics"):
            return await call_next(request)

        # 从请求中提取标识符
        client_ip = request.client.host if request.client else "unknown"

        # Token 端点特殊限流
        if path == "/token":
            allowed, remaining, reset_in = await token_endpoint_limiter.is_allowed(
                f"ip:{client_ip}"
            )
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Too many token requests. Please try again later.",
                    headers={
                        "X-RateLimit-Limit": str(token_endpoint_limiter.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_in),
                        "Retry-After": str(reset_in),
                    },
                )

        # 客户端级别限流
        client_id = _extract_client_id(request)
        if client_id:
            allowed, remaining, reset_in = await client_rate_limiter.is_allowed(
                f"client:{client_id}"
            )
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded for this client.",
                    headers={
                        "X-RateLimit-Limit": str(client_rate_limiter.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_in),
                        "Retry-After": str(reset_in),
                    },
                )

        response = await call_next(request)
        return response


def _extract_client_id(request: Request) -> str | None:
    """从请求中提取 client_id"""
    # 从 Authorization header (Bearer token)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.domain.federation.token_service import TokenManager
            claims = TokenManager().verify_access_token(auth[7:])
            aud = claims.get("aud", [])
            if isinstance(aud, list) and aud:
                return aud[0]
        except Exception:
            pass

    # 从 Basic auth
    if auth.startswith("Basic "):
        try:
            from base64 import b64decode
            decoded = b64decode(auth[6:]).decode()
            return decoded.split(":", 1)[0]
        except Exception:
            pass

    return None
