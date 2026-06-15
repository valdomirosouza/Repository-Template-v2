"""Structured API error model and exception handlers.

One envelope for every non-2xx response: a stable ``code``, a ``request_id``/``trace_id`` for
correlation, and a PII-masked ``detail``. Replaces FastAPI's default ``{"detail": ...}`` without
changing which condition yields which HTTP status.

Spec: specs/api/SPEC-API-001-error-model-and-request-correlation.md
ADR:  ADR-0076 (error model + correlation), ADR-0012 (PII masking), ADR-0004 (Observability)
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from opentelemetry import trace
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from src.guardrails.pii_filter import mask_text
from src.observability.request_context import get_request_id
from src.shared.config import settings

# Stable, published error codes (ADR-0076). Adding a code is backward-compatible; removing or
# renaming one is a breaking change requiring an API version bump (ADR-0024).
_STATUS_TO_CODE: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    503: "UNAVAILABLE",
}


class FieldError(BaseModel):
    """A single field-level validation problem."""

    field: str
    message: str


class ErrorResponse(BaseModel):
    """The one error envelope returned by every non-2xx response (ADR-0076)."""

    status: int
    code: str
    title: str
    detail: str | None = None
    request_id: str
    trace_id: str | None = None
    errors: list[FieldError] | None = None


def _code_for(status_code: int) -> str:
    if status_code in _STATUS_TO_CODE:
        return _STATUS_TO_CODE[status_code]
    return "INTERNAL_ERROR" if status_code >= 500 else "BAD_REQUEST"


def _title_for(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or get_request_id() or "unknown"


def _mask(text: str | None) -> str | None:
    if text is None:
        return None
    return mask_text(text) if settings.pii_masking_enabled else text


def _build(
    request: Request,
    status_code: int,
    *,
    detail: str | None = None,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
    code: str | None = None,
    title: str | None = None,
) -> JSONResponse:
    rid = _request_id(request)
    envelope = ErrorResponse(
        status=status_code,
        code=code or _code_for(status_code),
        title=title or _title_for(status_code),
        detail=_mask(detail),
        request_id=rid,
        trace_id=_trace_id(),
        errors=errors,
    )
    response = JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(exclude_none=True),
        headers=headers,
    )
    # Guarantee correlation on the error path regardless of middleware ordering.
    response.headers[settings.request_id_header] = rid
    return response


class AppError(Exception):
    """A typed domain error that maps directly to the envelope with an explicit, stable `code`.

    Use when the HTTP status alone does not determine the code (e.g. a 422 that is specifically
    ``IDEMPOTENCY_KEY_REUSED`` rather than a generic ``VALIDATION_ERROR``). ADR-0076/0077.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str | None = None,
        *,
        title: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or code)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.title = title
        self.headers = headers


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Map a typed AppError to the envelope, honouring its explicit code/title (ADR-0076)."""
    return _build(
        request,
        exc.status_code,
        detail=exc.detail,
        code=exc.code,
        title=exc.title,
        headers=dict(exc.headers or {}),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Map any HTTPException to the envelope, preserving its headers (e.g. Retry-After on 503)."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _build(request, exc.status_code, detail=detail, headers=dict(exc.headers or {}))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map request validation failures to 422 + a field-level errors[] list (FR-02)."""
    field_errors: list[FieldError] = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body",)]
        field_errors.append(
            FieldError(field=".".join(loc) or "request", message=str(_mask(err.get("msg", ""))))
        )
    return _build(request, 422, detail="Request validation failed.", errors=field_errors)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Map slowapi 429s to the envelope, preserving Retry-After / X-RateLimit headers (FR-08)."""
    headers: dict[str, str] = {}
    try:
        from slowapi import _rate_limit_exceeded_handler

        base = _rate_limit_exceeded_handler(request, exc)
        for name, value in base.headers.items():
            low = name.lower()
            if low == "retry-after" or low.startswith("x-ratelimit"):
                headers[name] = value
    except Exception:  # noqa: S110 - defensive: the limiter handler must never break error mapping
        pass
    return _build(request, 429, detail="Rate limit exceeded.", headers=headers)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: 500 with no internals/stack trace in the response (FR-03)."""
    return _build(request, 500, detail="Internal server error.")


def install_error_handlers(app: FastAPI) -> None:
    """Register all structured-error handlers on the app (call from main.py)."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)


__all__ = ["AppError", "ErrorResponse", "FieldError", "install_error_handlers"]
