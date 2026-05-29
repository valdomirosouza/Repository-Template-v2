"""Unit tests for the requests router — submit and status endpoints.

Spec: specs/system/request-pipeline.md
ADR:  ADR-0003 (Async API Strategy)

Uses FastAPI + ASGITransport + AsyncClient (same pattern as test_hitl_router.py).
No Kafka or Redis required — InMemoryRequestStore and InMemoryBroker are used.
All test inputs use clearly synthetic, obviously fake data.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.agents.request_store import InMemoryRequestStore
from src.api.rest.routers.requests import router
from src.shared.broker import InMemoryBroker

# ── App factory ───────────────────────────────────────────────────────────────


def _make_app(with_store: bool = True, with_broker: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    if with_store:
        app.state.request_store = InMemoryRequestStore()
    if with_broker:
        app.state.broker = InMemoryBroker()
    return app


# ── Submit ────────────────────────────────────────────────────────────────────


class TestSubmitRequest:
    @pytest.mark.asyncio
    async def test_submit_returns_202_with_queued_status(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/requests", json={"request_text": "summarise the quarterly report"}
            )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert "request_id" in body

    @pytest.mark.asyncio
    async def test_submit_publishes_event_to_broker(self) -> None:
        store = InMemoryRequestStore()
        broker = InMemoryBroker()
        app = _make_app()
        app.state.request_store = store
        app.state.broker = broker

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/v1/requests", json={"request_text": "analyse the sales data"})

        assert len(broker.published) == 1
        assert broker.published[0]["topic"] == "domain.request.created"

    @pytest.mark.asyncio
    async def test_submit_returns_503_when_store_unavailable(self) -> None:
        app = _make_app(with_store=False)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/v1/requests", json={"request_text": "any text"})
        assert response.status_code == 503


# ── Status ────────────────────────────────────────────────────────────────────


class TestGetRequestStatus:
    @pytest.mark.asyncio
    async def test_status_returns_200_for_known_request(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            post = await client.post("/v1/requests", json={"request_text": "process this"})
            request_id = post.json()["request_id"]
            response = await client.get(f"/v1/requests/{request_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["request_id"] == request_id
        assert body["status"] == "queued"

    @pytest.mark.asyncio
    async def test_status_returns_404_for_unknown_id(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/requests/does-not-exist")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_status_returns_503_when_store_unavailable(self) -> None:
        app = _make_app(with_store=False)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/requests/any-id")
        assert response.status_code == 503
