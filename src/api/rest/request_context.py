"""Request correlation middleware (X-Request-ID).

Accepts an inbound ``X-Request-ID`` (validated), or generates a UUIDv4, binds it into the
request-scoped context (read by the logger and error handlers), and echoes it on every response.

Spec: specs/api/SPEC-API-001-error-model-and-request-correlation.md
ADR:  ADR-0076 (Structured API error model + correlation)
"""

from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.observability.request_context import reset_request_id, set_request_id
from src.shared.config import settings

# Printable ASCII only, bounded length — a correlation id is an opaque token, never markup or PII.
_VALID_REQUEST_ID = re.compile(r"^[\x20-\x7e]+$")


def _resolve_request_id(raw: str | None) -> str:
    """Reuse a valid client-supplied id; otherwise mint a fresh UUIDv4 (FR-04)."""
    if raw and len(raw) <= settings.request_id_max_length and _VALID_REQUEST_ID.match(raw):
        return raw
    return str(uuid.uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a correlation id for the request and set ``X-Request-ID`` on the response.

    Added outermost so the id is in scope before any handler logs (FR-05/06). The id is also
    stashed on ``request.state.request_id`` for handlers that prefer the request object.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        header = settings.request_id_header
        request_id = _resolve_request_id(request.headers.get(header))
        request.state.request_id = request_id
        token = set_request_id(request_id)
        try:
            response: Response = await call_next(request)  # type: ignore[operator]
        finally:
            reset_request_id(token)
        response.headers[header] = request_id
        return response
