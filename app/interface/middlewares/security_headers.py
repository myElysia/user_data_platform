"""安全头中间件 — HSTS、CSP、防点击劫持等"""

from fastapi import FastAPI, Request, Response


def register_security_headers(app: FastAPI):
    """注册安全响应头中间件"""

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next) -> Response:
        response = await call_next(request)

        # HSTS — 强制 HTTPS（生产环境启用）
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )

        # 防点击劫持
        response.headers.setdefault("X-Frame-Options", "DENY")

        # 防 MIME 类型嗅探
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # 启用浏览器 XSS 过滤
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")

        # 引用策略
        response.headers.setdefault(
            "Referrer-Policy",
            "strict-origin-when-cross-origin",
        )

        # 权限策略
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )

        # CSP — 内容安全策略
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;",
        )

        # 移除可能泄露内部信息的头（MutableHeaders 无 pop，用条件删除）
        for header in ("X-Powered-By", "Server"):
            if header in response.headers:
                del response.headers[header]

        return response