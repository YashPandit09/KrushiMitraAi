"""Security headers and a small in-memory rate limiter."""

from __future__ import annotations

import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The app is fully self-hosted (no CDNs, no third-party fonts or trackers), so the policy can be
# strict. Inline styles are allowed because the charting library sets style attributes.
APP_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'"
)
# FastAPI's interactive docs load Swagger UI / ReDoc from jsDelivr.
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "worker-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
DOCS_PATHS = ("/api/docs", "/api/redoc")

BASE_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"strict-origin-when-cross-origin",
    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    b"cross-origin-opener-policy": b"same-origin",
    b"cross-origin-resource-policy": b"same-origin",
}


class SecurityHeadersMiddleware:
    """Pure ASGI middleware (works with streaming and static responses)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        csp = DOCS_CSP if path.startswith(DOCS_PATHS) else APP_CSP
        https = scope.get("scheme") == "https"

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in BASE_HEADERS]
                headers.extend(BASE_HEADERS.items())
                headers.append((b"content-security-policy", csp.encode()))
                if https:
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RateLimiter:
    """Sliding-window limit per client IP. In-memory: fine for a single instance."""

    def __init__(self, limit: int, window_seconds: float = 60.0, max_clients: int = 50_000) -> None:
        self.limit = limit
        self.window = window_seconds
        self.max_clients = max_clients
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > self.max_clients:  # bound memory under abuse
                self._hits.clear()
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry = max(1, math.ceil(self.window - (now - hits[0])))
                raise HTTPException(status_code=429, detail="Too many requests", headers={"Retry-After": str(retry)})
            hits.append(now)


def client_ip(request: Request) -> str:
    # uvicorn applies X-Forwarded-For only from trusted proxies (FORWARDED_ALLOW_IPS), so
    # request.client already holds the real address behind a configured reverse proxy.
    return request.client.host if request.client else "unknown"
