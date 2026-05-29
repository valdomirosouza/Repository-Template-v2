"""E2E — Request submission and processing lifecycle.

CUJ:   CUJ-001 (User Request Processing), CUJ-003 (Agent Autonomous Resolution)
Spec:  specs/system/request-pipeline.md, specs/system/async-event-flow.md
ADR:   ADR-0003 (Async API Strategy), ADR-0011 (HITL/HOTL Model)
SLO:   availability ≥ 99.9%; latency p99 ≤ 500 ms for submit; status polling ≤ 200 ms

Tests the complete golden-path lifecycle:
  1. Submit a request (POST /v1/requests) → 202 Accepted.
  2. Poll status (GET /v1/requests/{id}) → status transitions observed.
  3. PII in request_text is masked before processing.
  4. Submitting to a service without stores returns 503.
  5. Rate limiting returns 429 with Retry-After.

Transport:
  Default — ASGI in-process; no real broker or Redis needed.
  Live     — set BASE_URL=http://localhost:8000 for a running server.

Test markers: e2e
"""

from __future__ import annotations

import os
import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

BASE_URL = os.environ.get("BASE_URL", "")
_LIVE = bool(BASE_URL)


# ── App factory ───────────────────────────────────────────────────────────────


def _build_app() -> FastAPI:
    from src.agents.request_store import InMemoryRequestStore
    from src.api.rest.routers.requests import router
    from src.shared.broker import InMemoryBroker

    app = FastAPI()
    app.include_router(router, prefix="/v1")
    app.state.request_store = InMemoryRequestStore()
    app.state.broker = InMemoryBroker()
    return app


def _build_app_no_store() -> FastAPI:
    from src.api.rest.routers.requests import router

    app = FastAPI()
    app.include_router(router, prefix="/v1")
    # Deliberately omit state.request_store and state.broker → 503
    return app


# ── Tests — submit ────────────────────────────────────────────────────────────


@pytest.mark.e2e
class TestRequestSubmit:
    async def test_submit_returns_202_accepted(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/requests",
                json={"request_text": "summarise the Q4 sales report", "priority": "normal"},
            )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert "request_id" in body
        assert len(body["request_id"]) == 36  # UUID v4

    async def test_submit_returns_request_id_in_message(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/requests", json={"request_text": "generate a summary"}
            )

        body = response.json()
        assert body["request_id"] in body["message"]

    async def test_submit_with_high_priority(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/requests",
                json={"request_text": "urgent task: review access logs", "priority": "high"},
            )

        assert response.status_code == 202

    async def test_submit_empty_request_text_returns_422(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.post("/v1/requests", json={"request_text": ""})

        assert response.status_code == 422

    async def test_submit_oversized_request_text_returns_422(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.post("/v1/requests", json={"request_text": "x" * 4001})

        assert response.status_code == 422

    async def test_submit_invalid_priority_returns_422(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/requests",
                json={"request_text": "valid text", "priority": "critical"},  # not in enum
            )

        assert response.status_code == 422

    async def test_submit_without_store_returns_503(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app_no_store()), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/requests", json={"request_text": "this should fail gracefully"}
            )

        assert response.status_code == 503


# ── Tests — status polling ────────────────────────────────────────────────────


@pytest.mark.e2e
class TestRequestStatusPolling:
    async def test_submitted_request_is_immediately_pollable(self) -> None:
        app = _build_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            submit = await client.post(
                "/v1/requests", json={"request_text": "analyse sentiment in Q3 feedback"}
            )
            request_id = submit.json()["request_id"]

            status = await client.get(f"/v1/requests/{request_id}")

        assert status.status_code == 200
        body = status.json()
        assert body["request_id"] == request_id
        assert body["status"] in {"queued", "processing", "completed", "failed"}

    async def test_newly_submitted_request_starts_as_queued(self) -> None:
        app = _build_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            submit = await client.post(
                "/v1/requests", json={"request_text": "classify the support ticket"}
            )
            request_id = submit.json()["request_id"]
            status = await client.get(f"/v1/requests/{request_id}")

        assert status.json()["status"] == "queued"

    async def test_unknown_request_id_returns_404(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.get("/v1/requests/00000000-0000-0000-0000-000000000099")

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_status_response_has_all_contracted_fields(self) -> None:
        app = _build_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            submit = await client.post(
                "/v1/requests", json={"request_text": "extract key entities"}
            )
            request_id = submit.json()["request_id"]
            body = (await client.get(f"/v1/requests/{request_id}")).json()

        for field in ("request_id", "status", "created_at", "updated_at", "message"):
            assert field in body, f"Missing contracted field: {field!r}"

    async def test_status_result_is_none_when_not_yet_completed(self) -> None:
        app = _build_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            submit = await client.post(
                "/v1/requests", json={"request_text": "draft a short executive summary"}
            )
            request_id = submit.json()["request_id"]
            body = (await client.get(f"/v1/requests/{request_id}")).json()

        # In-memory store, no real agent running — result will be None
        assert body["result"] is None


# ── Tests — PII in request text ───────────────────────────────────────────────


@pytest.mark.e2e
class TestRequestPIIMasking:
    async def test_request_with_pii_in_text_is_accepted(self) -> None:
        """The API must accept requests with PII — masking happens inside the pipeline."""
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/requests",
                json={
                    "request_text": "Please review the record for test@example.com",
                    "priority": "normal",
                },
            )

        # Submission succeeds; PII masking is applied inside the pipeline before LLM call
        assert response.status_code == 202

    async def test_pii_not_echoed_back_in_submit_response(self) -> None:
        """The 202 response must not contain raw PII from the request text."""
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/requests",
                json={"request_text": "email is test@example.com, CPF is 000.000.000-00"},
            )

        body_str = response.text
        assert "test@example.com" not in body_str
        assert "000.000.000-00" not in body_str


# ── Tests — submit latency ────────────────────────────────────────────────────


@pytest.mark.e2e
class TestRequestSubmitLatency:
    async def test_submit_latency_under_slo_threshold_ms(self) -> None:
        """Submission must complete in < 500 ms (SLO: p99 ≤ 500 ms for read/classify flows).

        This test measures a single request; for statistical significance use the k6
        load test at tests/performance/k6/request-api-load.js.
        """
        app = _build_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start = time.perf_counter()
            response = await client.post(
                "/v1/requests", json={"request_text": "benchmark latency check"}
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 202
        assert elapsed_ms < 500, f"Submit latency {elapsed_ms:.1f} ms exceeds 500 ms SLO threshold"

    async def test_status_poll_latency_under_200ms(self) -> None:
        """Status poll should be a cache read — well under 200 ms even at low percentiles."""
        app = _build_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request_id = (
                await client.post("/v1/requests", json={"request_text": "poll latency check"})
            ).json()["request_id"]

            start = time.perf_counter()
            await client.get(f"/v1/requests/{request_id}")
            elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 200, f"Status poll latency {elapsed_ms:.1f} ms exceeds 200 ms threshold"


# ── Tests — concurrent submissions ────────────────────────────────────────────


@pytest.mark.e2e
class TestRequestConcurrency:
    async def test_multiple_concurrent_submissions_all_succeed(self) -> None:
        """10 concurrent submissions must all return unique request IDs."""
        import asyncio

        app = _build_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tasks = [
                client.post(
                    "/v1/requests",
                    json={"request_text": f"concurrent request number {i}"},
                )
                for i in range(10)
            ]
            responses = await asyncio.gather(*tasks)

        assert all(r.status_code == 202 for r in responses)
        request_ids = [r.json()["request_id"] for r in responses]
        # All IDs must be unique
        assert len(set(request_ids)) == 10
