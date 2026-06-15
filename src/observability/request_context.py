"""Request-scoped correlation id propagation (X-Request-ID).

A `ContextVar` carries the current request's correlation id across the async call stack so the
structured logger and the error handlers can stamp it without threading it through every call.

Spec: specs/api/SPEC-API-001-error-model-and-request-correlation.md
ADR:  ADR-0076 (Structured API error model + correlation), ADR-0004 (Observability)
"""

from __future__ import annotations

from contextvars import ContextVar, Token

# None when no request is in scope (e.g. background tasks, startup).
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> Token[str | None]:
    """Bind the correlation id for the current context; returns a token for :func:`reset`."""
    return _request_id.set(request_id)


def get_request_id() -> str | None:
    """Return the correlation id bound to the current context, or None."""
    return _request_id.get()


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous correlation id (call in a finally to avoid cross-request leakage)."""
    _request_id.reset(token)
