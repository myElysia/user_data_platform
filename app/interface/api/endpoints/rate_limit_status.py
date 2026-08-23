"""限流状态端点"""

from fastapi import APIRouter, Request

from app.interface.middlewares.rate_limit import (
    client_rate_limiter,
    user_rate_limiter,
)

router = APIRouter(prefix="/rate-limit", tags=["Rate Limit"])


@router.get("/status")
async def rate_limit_status(request: Request):
    """查询当前客户端/用户的限流状态"""
    client_ip = request.client.host if request.client else "unknown"
    client_id = request.headers.get("X-Client-Id", "")

    results = {
        "ip_based": await client_rate_limiter.get_usage(f"ip:{client_ip}"),
    }

    if client_id:
        results["client_based"] = await client_rate_limiter.get_usage(
            f"client:{client_id}"
        )

    return results
