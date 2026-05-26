"""Unit tests for the HITL router endpoints.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.agents.hitl_gateway import HITLGateway, HITLRequest
from src.agents.hitl_store import InMemoryHITLStore
from src.api.rest.routers.hitl import router
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_app(with_gateway: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/hitl")
    if with_gateway:
        audit = AuditLogger(InMemoryAuditStorage())
        app.state.hitl_gateway = HITLGateway(
            audit_logger=audit,
            broker=None,
            store=InMemoryHITLStore(),
        )
    return app


def _make_hitl_request() -> HITLRequest:
    now = datetime.now(UTC)
    return HITLRequest(
        request_id=str(uuid.uuid4()),
        agent_id="agent-test",
        action_type="test_action",
        action_parameters={},
        risk_score=0.5,
        context_summary="synthetic context",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


# ── Status endpoint ───────────────────────────────────────────────────────────


class TestHITLStatus:
    @pytest.mark.asyncio
    async def test_returns_200_with_zero_pending(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/hitl/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "operational"
        assert body["pending_count"] == 0

    @pytest.mark.asyncio
    async def test_returns_503_when_gateway_not_initialized(self):
        app = _make_app(with_gateway=False)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/hitl/status")
        assert response.status_code == 503


# ── Decision endpoint ─────────────────────────────────────────────────────────


class TestHITLDecision:
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_request_id(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/hitl/requests/{uuid.uuid4()}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": "Looks good to me.",
                    "approver_id": "reviewer-01",
                },
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_200_for_valid_approval(self):
        app = _make_app()
        gateway: HITLGateway = app.state.hitl_gateway
        req = _make_hitl_request()
        await gateway.submit_for_approval(req)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/hitl/requests/{req.request_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": "Reviewed and approved.",
                    "approver_id": "reviewer-01",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["decision"] == "APPROVED"
        assert body["request_id"] == req.request_id
