"""HTTP Golden Signals middleware (W12-T4, issue #357 — FEAT-001).

``record_request()`` in ``src/observability/metrics.py`` defined ``http_requests_total`` and
``http_request_duration_seconds`` but had no caller, so Traffic, Errors and Latency for the API
were never populated and the governance SLO endpoint could not report availability.

Pure ASGI middleware (no BaseHTTPMiddleware, so streaming responses and background tasks are
untouched). The ``path`` label is the *route template* (``/v1/requests/{request_id}``), never the
raw path, which keeps label cardinality bounded and avoids leaking identifiers into metrics.

Spec: specs/features/FEAT-001/feature-spec.md · specs/observability/golden-signals.md
ADR:  ADR-0006 (observability), ADR-0043 (no PII in telemetry)
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from src.observability.metrics import record_request
from src.shared.config import settings

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

EXCLUDED_PATHS: frozenset[str] = frozenset({"/metrics"})


def route_template(scope: Scope) -> str:
    """Route template after routing, else a bounded placeholder (404s, unmatched paths)."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        root = scope.get("root_path") or ""
        return f"{root}{path}" if root else path
    return "<unmatched>"


class GoldenSignalsMiddleware:
    """Record method / route template / status / duration for every HTTP request."""

    def __init__(self, app: ASGIApp, service: str | None = None) -> None:
        self.app = app
        self._service = service or settings.service_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or scope.get("path") in EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500  # if the app raises before responding, count it as a server error

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            record_request(
                self._service,
                str(scope.get("method", "GET")),
                route_template(scope),
                status_code,
                time.perf_counter() - start,
            )
