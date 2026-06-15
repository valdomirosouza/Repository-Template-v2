"""Unit tests for the structured error model + X-Request-ID correlation.

Covers SPEC-API-001 acceptance criteria AC-01..AC-08 (ADR-0076) against an isolated app so the
middleware + exception handlers are exercised without infra or auth.

Spec: specs/api/SPEC-API-001-error-model-and-request-correlation.md
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.testclient import TestClient

from src.api.rest.errors import install_error_handlers, rate_limit_handler
from src.api.rest.request_context import RequestContextMiddleware
from src.shared.config import settings

pytestmark = pytest.mark.unit

HDR = settings.request_id_header


class _Body(BaseModel):
    name: str


def _make_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ok")
    async def ok() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/missing")
    async def missing() -> None:
        raise HTTPException(status_code=404, detail="Request 550e8400 not found.")

    @app.get("/pii")
    async def pii() -> None:
        raise HTTPException(status_code=400, detail="Bad email joe@example.com in payload")

    @app.get("/capacity")
    async def capacity() -> None:
        raise HTTPException(
            status_code=503, detail="Agent capacity exhausted", headers={"Retry-After": "5"}
        )

    @app.post("/things")
    async def things(body: _Body) -> dict[str, str]:
        return {"name": body.name}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail that must not leak")

    return app


# ---------------------------------------------------------------- AC-01 / AC-05


def test_http_exception_returns_envelope_and_request_id_header() -> None:
    client = TestClient(_make_app())
    r = client.get("/missing")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "NOT_FOUND"
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert "detail" in body
    # AC-05: a request id is generated and present in both header and envelope, and they match.
    assert HDR in r.headers
    assert body["request_id"] == r.headers[HDR]
    uuid.UUID(r.headers[HDR])  # generated id is a valid UUID


def test_success_response_also_carries_request_id() -> None:
    client = TestClient(_make_app())
    r = client.get("/ok")
    assert r.status_code == 200
    assert HDR in r.headers


# ---------------------------------------------------------------- AC-04


def test_inbound_request_id_is_echoed_and_used() -> None:
    client = TestClient(_make_app())
    r = client.get("/missing", headers={HDR: "abc123"})
    assert r.headers[HDR] == "abc123"
    assert r.json()["request_id"] == "abc123"


def test_invalid_inbound_request_id_is_replaced() -> None:
    client = TestClient(_make_app())
    bad = "x" * (settings.request_id_max_length + 1)
    r = client.get("/ok", headers={HDR: bad})
    assert r.headers[HDR] != bad
    uuid.UUID(r.headers[HDR])  # replaced with a generated UUID


# ---------------------------------------------------------------- AC-02


def test_validation_error_maps_to_422_with_field_errors() -> None:
    client = TestClient(_make_app())
    r = client.post("/things", json={})  # missing required 'name'
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body["errors"], list) and body["errors"]
    assert any(e["field"] == "name" for e in body["errors"])


# ---------------------------------------------------------------- AC-03


def test_unhandled_exception_returns_500_without_internals() -> None:
    client = TestClient(_make_app(), raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in r.text  # FR-03: no internals/stack trace leaked
    assert HDR in r.headers


# ---------------------------------------------------------------- AC-06


def test_pii_in_detail_is_masked() -> None:
    assert settings.pii_masking_enabled  # precondition for this AC
    client = TestClient(_make_app())
    r = client.get("/pii")
    assert "joe@example.com" not in r.text
    assert "[EMAIL]" in r.json()["detail"]


# ---------------------------------------------------------------- AC-07


def test_capacity_503_maps_to_unavailable_and_preserves_retry_after() -> None:
    client = TestClient(_make_app())
    r = client.get("/capacity")
    assert r.status_code == 503
    assert r.json()["code"] == "UNAVAILABLE"
    assert r.headers.get("Retry-After") == "5"


@pytest.mark.asyncio
async def test_rate_limit_handler_maps_to_rate_limited() -> None:
    from slowapi.errors import RateLimitExceeded
    from starlette.requests import Request

    scope = {"type": "http", "headers": [], "state": {}}
    request = Request(scope)

    class _Limit:
        error_message = "rate limit"
        limit = "1/minute"

    exc = RateLimitExceeded(_Limit())  # type: ignore[arg-type]
    resp = await rate_limit_handler(request, exc)
    assert resp.status_code == 429
    import json

    assert json.loads(bytes(resp.body))["code"] == "RATE_LIMITED"


# ---------------------------------------------------------------- request-context unit


def test_request_context_var_set_get_reset() -> None:
    from src.observability.request_context import get_request_id, reset_request_id, set_request_id

    assert get_request_id() is None
    token = set_request_id("rid-1")
    assert get_request_id() == "rid-1"
    reset_request_id(token)
    assert get_request_id() is None


def test_logger_record_includes_request_id() -> None:
    from src.observability.logger import StructuredLogger
    from src.observability.request_context import reset_request_id, set_request_id

    token = set_request_id("rid-log")
    try:
        record = StructuredLogger("test", "test")._build_record("info", "msg", {})
        assert record["request_id"] == "rid-log"
    finally:
        reset_request_id(token)
