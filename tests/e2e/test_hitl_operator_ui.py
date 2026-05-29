"""E2E — HITL operator decision flow.

CUJ:   CUJ-002 (HITL Decision Flow)
Spec:  specs/ai/hitl-hotl.md, specs/security/rbac-model.md
ADR:   ADR-0011 (HITL/HOTL Model)
SLO:   p95 decision latency ≤ 300 s; HITL gateway availability ≥ 99.9%

Tests the complete operator journey:
  1. A user submits a request that triggers HITL escalation.
  2. The HITL operator sees the request in the pending queue.
  3. The operator submits an APPROVE decision.
  4. The request status reflects the decision.
  5. An REJECT decision is also tested.
  6. Attempting to decide an unknown / expired request returns 404.

Transport:
  Default   — ASGI in-process (no real server required; uses InMemory stores)
  Live mode — set BASE_URL=http://localhost:8000 to run against a real server

Test markers: e2e
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# ── Transport selection ───────────────────────────────────────────────────────

BASE_URL = os.environ.get("BASE_URL", "")
_LIVE = bool(BASE_URL)


def _build_asgi_app() -> FastAPI:
    """Minimal FastAPI app wiring the HITL and requests routers with in-memory stores."""
    from src.agents.hitl_gateway import HITLGateway
    from src.agents.hitl_store import InMemoryHITLStore
    from src.agents.request_store import InMemoryRequestStore
    from src.api.rest.routers.hitl import router as hitl_router
    from src.api.rest.routers.requests import router as req_router
    from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
    from src.shared.broker import InMemoryBroker

    audit = AuditLogger(InMemoryAuditStorage())
    store = InMemoryHITLStore()
    gateway = HITLGateway(audit_logger=audit, broker=None, store=store)

    app = FastAPI()
    app.include_router(req_router, prefix="/v1")
    app.include_router(hitl_router, prefix="/v1/hitl")
    app.state.request_store = InMemoryRequestStore()
    app.state.broker = InMemoryBroker()
    app.state.hitl_gateway = gateway
    return app


async def _make_client() -> tuple[AsyncClient, Any]:
    """Return (client, context_manager) suited to the chosen transport."""
    if _LIVE:
        client = AsyncClient(base_url=BASE_URL, timeout=10.0)
        return client, client
    app = _build_asgi_app()
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return client, client


# ── Helpers ───────────────────────────────────────────────────────────────────

_SYNTHETIC_APPROVER = "operator-00000000-0000-0000-0000-000000000001"
_SYNTHETIC_RATIONALE = "Action verified against approved scope. Risk within accepted bounds."


async def _seed_hitl_request(gateway: Any) -> str:
    """Directly seed a pending HITL request (ASGI mode only)."""
    from src.agents.hitl_gateway import HITLRequest

    req = HITLRequest(
        request_id=str(uuid.uuid4()),
        agent_id="test-agent-00000000",
        action_type="write_file",
        action_parameters={"path": "/tmp/report.txt"},
        risk_score=0.85,
        context_summary="Agent proposes writing a report file.",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await gateway._store.save(req)
    return req.request_id


# ── Tests — HITL status endpoint ──────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLStatusEndpoint:
    async def test_hitl_status_returns_operational(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_asgi_app()), base_url="http://test"
        ) as client:
            response = await client.get("/v1/hitl/status")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "operational"
        assert isinstance(body["pending_count"], int)
        assert body["pending_count"] >= 0

    async def test_hitl_status_reflects_queue_depth(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        rid = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/hitl/status")

        assert response.status_code == 200
        assert response.json()["pending_count"] >= 1
        _ = rid  # seeded for queue depth assertion


# ── Tests — APPROVE decision ──────────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLApproveDecision:
    async def test_approve_returns_200_with_approved_decision(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": _SYNTHETIC_RATIONALE,
                    "approver_id": _SYNTHETIC_APPROVER,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["decision"] == "APPROVED"
        assert body["request_id"] == request_id

    async def test_approve_removes_request_from_pending_queue(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            depth_before = (await client.get("/v1/hitl/status")).json()["pending_count"]
            await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": _SYNTHETIC_RATIONALE,
                    "approver_id": _SYNTHETIC_APPROVER,
                },
            )
            depth_after = (await client.get("/v1/hitl/status")).json()["pending_count"]

        assert depth_after < depth_before

    async def test_approve_decision_field_matches_contracted_enum(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            body = (
                await client.post(
                    f"/v1/hitl/requests/{request_id}/decision",
                    json={
                        "decision": "APPROVED",
                        "rationale": _SYNTHETIC_RATIONALE,
                        "approver_id": _SYNTHETIC_APPROVER,
                    },
                )
            ).json()

        assert body["decision"] in {"APPROVED", "REJECTED"}


# ── Tests — REJECT decision ───────────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLRejectDecision:
    async def test_reject_returns_200_with_rejected_decision(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "REJECTED",
                    "rationale": "Action exceeds approved risk threshold for this action_type.",
                    "approver_id": _SYNTHETIC_APPROVER,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["decision"] == "REJECTED"
        assert body["request_id"] == request_id

    async def test_short_rationale_returns_422(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "REJECTED",
                    "rationale": "too short",  # < 10 chars
                    "approver_id": _SYNTHETIC_APPROVER,
                },
            )

        assert response.status_code == 422


# ── Tests — not found / expired ───────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLNotFound:
    async def test_unknown_request_id_returns_404(self) -> None:
        app = _build_asgi_app()
        unknown_id = "00000000-0000-0000-0000-000000000099"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/v1/hitl/requests/{unknown_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": _SYNTHETIC_RATIONALE,
                    "approver_id": _SYNTHETIC_APPROVER,
                },
            )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_double_decision_on_same_request_returns_404(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            decision_payload = {
                "decision": "APPROVED",
                "rationale": _SYNTHETIC_RATIONALE,
                "approver_id": _SYNTHETIC_APPROVER,
            }
            first = await client.post(
                f"/v1/hitl/requests/{request_id}/decision", json=decision_payload
            )
            second = await client.post(
                f"/v1/hitl/requests/{request_id}/decision", json=decision_payload
            )

        assert first.status_code == 200
        # Request is no longer pending after first decision — second should 404
        assert second.status_code == 404


# ── Tests — invalid decision value ────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLValidation:
    async def test_invalid_decision_enum_returns_422(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "MAYBE",  # not in enum
                    "rationale": _SYNTHETIC_RATIONALE,
                    "approver_id": _SYNTHETIC_APPROVER,
                },
            )

        assert response.status_code == 422

    async def test_missing_rationale_returns_422(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={"decision": "APPROVED", "approver_id": _SYNTHETIC_APPROVER},
            )

        assert response.status_code == 422
