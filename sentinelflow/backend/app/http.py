from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings
from app.errors import error_response


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = monotonic()
        bucket = self.requests[key]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True


def install_http_middleware(app: FastAPI, settings: Settings) -> None:
    limiter = InMemoryRateLimiter(
        limit=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def harden_requests(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        request_id = getattr(request.state, "request_id", "req_unknown")
        if content_length and int(content_length) > settings.MAX_REQUEST_BYTES:
            return error_response(
                code="REQUEST_TOO_LARGE",
                message="Request exceeded the allowed payload size.",
                request_id=request_id,
                status_code=413,
            )

        client_host = request.headers.get("x-forwarded-for")
        if client_host:
            client_host = client_host.split(",", maxsplit=1)[0].strip()
        elif request.client is not None:
            client_host = request.client.host
        else:
            client_host = "unknown"
        if not limiter.allow(client_host):
            return error_response(
                code="RATE_LIMITED",
                message="Too many requests. Try again later.",
                request_id=request_id,
                status_code=429,
            )

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.url.path.endswith("/stream"):
            response.headers["X-Accel-Buffering"] = "no"
        return response
