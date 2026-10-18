from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable
from time import monotonic
from uuid import uuid4

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
        self.requests: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = monotonic()
        bucket = self.requests.get(key)
        if bucket is None:
            bucket = deque()
            self.requests[key] = bucket
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        if len(self.requests) > 10_000:
            self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        stale_keys = [
            k for k, b in self.requests.items() if not b or now - b[-1] > self.window_seconds
        ]
        for k in stale_keys:
            self.requests.pop(k, None)


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
        request_id = getattr(request.state, "request_id", None) or request.headers.get(
            "x-request-id", f"req_{uuid4().hex[:12]}"
        )
        request.state.request_id = request_id
        if content_length and int(content_length) > settings.MAX_REQUEST_BYTES:
            return error_response(
                code="REQUEST_TOO_LARGE",
                message="Request exceeded the allowed payload size.",
                request_id=request_id,
                status_code=413,
            )

        client_host = request.headers.get("x-real-ip")
        if not client_host:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                client_host = forwarded.split(",")[-1].strip()
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
        if str(request.scope.get("path", "")).endswith("/stream"):
            response.headers["X-Accel-Buffering"] = "no"
        return response
