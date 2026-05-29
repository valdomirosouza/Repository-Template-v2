"""Unit tests for the HITL router endpoints.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)
Threat model: REM-001 (operator authentication on the decision endpoint)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.agents.hitl_gateway import HITLGateway, HITLRequest
from src.agents.hitl_store import InMemoryHITLStore
from src.api.rest.routers.hitl import router
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
from src.shared.config import settings

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_app(with_gateway: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/hitl")
    if with_gateway:
        storage = InMemoryAuditStorage()
        app.state.hitl_gateway = HITLGateway(
            audit_logger=AuditLogger(storage),
            broker=None,
            store=InMemoryHITLStore(),
        )
        app.state._audit_storage = storage  # exposed for assertions
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


def _token(
    sub: str = "reviewer-01", role: str | None = "hitl-operator", expires_in: int = 3600
) -> str:
    payload: dict = {"sub": sub, "exp": datetime.now(UTC) + timedelta(seconds=expires_in)}
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _auth(
    sub: str = "reviewer-01", role: str | None = "hitl-operator", expires_in: int = 3600
) -> dict:
    return {"Authorization": f"Bearer {_token(sub, role, expires_in)}"}


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


# ── Decision endpoint — authentication & authorization (REM-001) ───────────────


class TestHITLDecisionAuth:
    @pytest.mark.asyncio
    async def test_rejects_missing_token(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/hitl/requests/{uuid.uuid4()}/decision",
                json={"decision": "APPROVED", "rationale": "Looks good to me."},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_malformed_token(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/hitl/requests/{uuid.uuid4()}/decision",
                json={"decision": "APPROVED", "rationale": "Looks good to me."},
                headers={"Authorization": "Bearer not-a-real-jwt"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_expired_token(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/hitl/requests/{uuid.uuid4()}/decision",
                json={"decision": "APPROVED", "rationale": "Looks good to me."},
                headers=_auth(expires_in=-10),
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_non_operator_role(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/hitl/requests/{uuid.uuid4()}/decision",
                json={"decision": "APPROVED", "rationale": "Looks good to me."},
                headers=_auth(role="viewer"),
            )
        assert response.status_code == 403


# ── Decision endpoint — behavior ───────────────────────────────────────────────


class TestHITLDecision:
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_request_id(self):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/hitl/requests/{uuid.uuid4()}/decision",
                json={"decision": "APPROVED", "rationale": "Looks good to me."},
                headers=_auth(),
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
                json={"decision": "APPROVED", "rationale": "Reviewed and approved."},
                headers=_auth(),
            )
        assert response.status_code == 200
        body = response.json()
        assert body["decision"] == "APPROVED"
        assert body["request_id"] == req.request_id

    @pytest.mark.asyncio
    async def test_approver_identity_comes_from_token_not_body(self):
        """The audit trail must record the token subject, never a body-supplied identity."""
        app = _make_app()
        gateway: HITLGateway = app.state.hitl_gateway
        req = _make_hitl_request()
        await gateway.submit_for_approval(req)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/hitl/requests/{req.request_id}/decision",
                # A spoofed approver_id in the body must be ignored.
                json={
                    "decision": "APPROVED",
                    "rationale": "Reviewed and approved.",
                    "approver_id": "attacker",
                },
                headers=_auth(sub="alice@corp"),
            )
        assert response.status_code == 200

        storage = app.state._audit_storage
        approvers = [e.approver_id for e in storage._records if e.approver_id]
        assert "alice@corp" in approvers
        assert "attacker" not in approvers
