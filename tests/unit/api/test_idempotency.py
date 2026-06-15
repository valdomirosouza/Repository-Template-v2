"""Unit tests for idempotency keys on POST /v1/requests.

Covers SPEC-API-002 acceptance criteria AC-01..AC-06 (ADR-0077) plus the store's claim semantics.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.agents.idempotency_store import (
    IdempotencyRecord,
    InMemoryIdempotencyStore,
    fingerprint_body,
)
from src.agents.request_store import InMemoryRequestStore
from src.api.rest.errors import install_error_handlers
from src.api.rest.routers import requests as requests_router
from src.shared.broker import InMemoryBroker

pytestmark = pytest.mark.unit

KEY = "test-key-12345"
BODY = {"request_text": "do a thing", "priority": "normal"}


def _make_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(requests_router.router, prefix="/v1")
    app.state.request_store = InMemoryRequestStore()
    app.state.broker = InMemoryBroker()
    app.state.idempotency_store = InMemoryIdempotencyStore()
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ------------------------------------------------------------------ AC-01 / AC-02


@pytest.mark.asyncio
async def test_first_call_records_then_replays_same_request_id() -> None:
    app = _make_app()
    async with _client(app) as client:
        r1 = await client.post("/v1/requests", json=BODY, headers={"Idempotency-Key": KEY})
        assert r1.status_code == 202
        rid = r1.json()["request_id"]

        r2 = await client.post("/v1/requests", json=BODY, headers={"Idempotency-Key": KEY})
        assert r2.status_code == 202
        assert r2.json()["request_id"] == rid  # AC-02: same id, no new request
        assert r2.headers.get("Idempotency-Replayed") == "true"


# ------------------------------------------------------------------ AC-03


@pytest.mark.asyncio
async def test_same_key_different_body_is_rejected() -> None:
    app = _make_app()
    async with _client(app) as client:
        await client.post("/v1/requests", json=BODY, headers={"Idempotency-Key": KEY})
        r = await client.post(
            "/v1/requests",
            json={"request_text": "a DIFFERENT thing", "priority": "normal"},
            headers={"Idempotency-Key": KEY},
        )
        assert r.status_code == 422
        assert r.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


# ------------------------------------------------------------------ AC-04


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_key", ["short", "x" * 201, "bad\nkey\twith\x00control"])
async def test_invalid_key_is_422(bad_key: str) -> None:
    app = _make_app()
    async with _client(app) as client:
        r = await client.post("/v1/requests", json=BODY, headers={"Idempotency-Key": bad_key})
        assert r.status_code == 422
        assert r.json()["code"] == "VALIDATION_ERROR"


# ------------------------------------------------------------------ AC-05


@pytest.mark.asyncio
async def test_no_key_creates_distinct_requests() -> None:
    app = _make_app()
    async with _client(app) as client:
        r1 = await client.post("/v1/requests", json=BODY)
        r2 = await client.post("/v1/requests", json=BODY)
        assert r1.json()["request_id"] != r2.json()["request_id"]


# ------------------------------------------------------------------ AC-06


@pytest.mark.asyncio
async def test_concurrent_identical_keys_resolve_to_one_request() -> None:
    app = _make_app()
    async with _client(app) as client:
        results = await asyncio.gather(
            *[
                client.post("/v1/requests", json=BODY, headers={"Idempotency-Key": "race-key-001"})
                for _ in range(5)
            ]
        )
        ids = {r.json()["request_id"] for r in results}
        assert all(r.status_code == 202 for r in results)
        assert len(ids) == 1  # exactly one request_id won the claim


# ------------------------------------------------------------------ store unit


@pytest.mark.asyncio
async def test_inmemory_store_claim_is_atomic() -> None:
    store = InMemoryIdempotencyStore()
    rec_a = IdempotencyRecord("id-a", "fp", datetime.now(UTC))
    rec_b = IdempotencyRecord("id-b", "fp", datetime.now(UTC))
    got_a, created_a = await store.claim("k", rec_a)
    got_b, created_b = await store.claim("k", rec_b)
    assert created_a is True and got_a.request_id == "id-a"
    assert created_b is False and got_b.request_id == "id-a"  # second claim sees the winner
    await store.release("k")
    _, created_c = await store.claim("k", rec_b)
    assert created_c is True  # released, so re-claimable


def test_fingerprint_is_stable_and_body_sensitive() -> None:
    a = fingerprint_body({"request_text": "x", "priority": "normal"})
    b = fingerprint_body({"request_text": "x", "priority": "normal"})
    c = fingerprint_body({"request_text": "y", "priority": "normal"})
    assert a == b and a != c
