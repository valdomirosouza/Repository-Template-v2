"""Unit tests for the runs router — GET /v1/runs/{request_id}.

Spec: specs/api/SPEC-API-004-runs-trace-and-slo-status.md
ADR:  ADR-0076 (structured error model), ADR-0011 (human oversight)

Uses FastAPI + ASGITransport + AsyncClient with in-memory stores (same pattern as
test_hitl_router.py / test_requests_router.py). All inputs are obviously synthetic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.agents.request_store import InMemoryRequestStore, RequestState
from src.api.rest.errors import install_error_handlers
from src.api.rest.routers.runs import router
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
from src.shared.config import settings
from src.shared.models import AuditEvent

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_app(with_store: bool = True, with_audit: bool = True) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)  # ADR-0076 envelope on 401/404
    app.include_router(router, prefix="/v1")
    if with_store:
        app.state.request_store = InMemoryRequestStore()
    if with_audit:
        storage = InMemoryAuditStorage()
        app.state.audit_logger = AuditLogger(storage)
        app.state._audit_storage = storage
    return app


def _token(sub: str = "viewer-01", role: str | None = "viewer", expires_in: int = 3600) -> str:
    payload: dict = {"sub": sub, "exp": datetime.now(UTC) + timedelta(seconds=expires_in)}
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _auth() -> dict:
    return {"Authorization": f"Bearer {_token()}"}


async def _seed_request(app: FastAPI, request_id: str, status: str = "completed") -> RequestState:
    now = datetime.now(UTC)
    state = RequestState(
        request_id=request_id,
        status=status,
        created_at=now - timedelta(minutes=1),
        updated_at=now,
        result={"summary": "synthetic result"},
        error=None,
    )
    await app.state.request_store.save(state)
    return state


# ── Auth ──────────────────────────────────────────────────────────────────────


class TestRunsAuth:
    @pytest.mark.asyncio
    async def test_rejects_missing_token(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/runs/{uuid.uuid4()}")
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_rejects_malformed_token(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/v1/runs/{uuid.uuid4()}",
                headers={"Authorization": "Bearer not-a-jwt"},
            )
        assert response.status_code == 401


# ── Behaviour ───────────────────────────────────────────────────────────────────


class TestRunsTrace:
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_request(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/runs/{uuid.uuid4()}", headers=_auth())
        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_200_with_state_and_empty_timeline_when_no_events(self) -> None:
        app = _make_app()
        request_id = str(uuid.uuid4())
        await _seed_request(app, request_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/runs/{request_id}", headers=_auth())

        assert response.status_code == 200
        body = response.json()
        assert body["request_id"] == request_id
        assert body["status"] == "completed"
        assert body["result"] == {"summary": "synthetic result"}
        assert body["timeline"] == []
        # Honest flag: nothing could be associated → "none" (CLAUDE.md §3.6).
        assert body["timeline_association"] == "none"

    @pytest.mark.asyncio
    async def test_returns_real_timeline_from_matching_audit_metadata(self) -> None:
        app = _make_app()
        request_id = str(uuid.uuid4())
        await _seed_request(app, request_id)

        # An audit event whose metadata.request_id exactly matches → the only real association.
        await app.state.audit_logger.log_event(
            AuditEvent(
                event_type="hitl.request.submitted",
                agent_id="agent-test",
                action="test_action",
                outcome="PENDING",
                risk_score=0.5,
                metadata={"request_id": request_id},
            )
        )
        # An unrelated event must NOT appear in the timeline.
        await app.state.audit_logger.log_event(
            AuditEvent(
                event_type="agent.action.proposed",
                agent_id="agent-other",
                action="other_action",
                outcome="PENDING",
                metadata={"request_id": str(uuid.uuid4())},
            )
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/runs/{request_id}", headers=_auth())

        assert response.status_code == 200
        body = response.json()
        assert body["timeline_association"] == "metadata_request_id"
        assert len(body["timeline"]) == 1
        event = body["timeline"][0]
        assert event["event_type"] == "hitl.request.submitted"
        assert event["action"] == "test_action"
        assert event["outcome"] == "PENDING"

    @pytest.mark.asyncio
    async def test_returns_200_with_none_association_when_no_audit_logger(self) -> None:
        app = _make_app(with_audit=False)
        request_id = str(uuid.uuid4())
        await _seed_request(app, request_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/runs/{request_id}", headers=_auth())

        assert response.status_code == 200
        body = response.json()
        assert body["timeline"] == []
        assert body["timeline_association"] == "none"
