"""Pact provider verification — api-gateway satisfies frontend consumer contracts.

Spec:  docs/api/asyncapi/v2/migration-guide.md
ADR:   ADR-0022 (Testing Strategy §3), ADR-0024 (API Versioning Strategy)
Pact:  tests/contract/pacts/frontend-api_gateway.json

This file is the provider-side complement to test_rest_pact_consumer.py (Wave 6.5).
Where the consumer tests verified that our Pydantic *models* match the Pact shapes,
this file fires real HTTP requests through the FastAPI ASGI stack and asserts that
actual response bodies, status codes, and headers match each contracted interaction.

Strategy:
  - Each test class covers one Pact interaction by description.
  - A shared fixture spins up a FastAPI app with in-memory stores (no Docker required).
  - Provider state is established via direct store manipulation before each request.
  - Every assertion mirrors the Pact matchingRules (type, regex, integer).

Test markers: unit (no external services — uses ASGI transport)
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# ── Load Pact file ────────────────────────────────────────────────────────────

PACT_FILE = Path(__file__).parent / "pacts" / "frontend-api_gateway.json"
_PACT = json.loads(PACT_FILE.read_text())

# Index interactions by description for easy test lookup
_INTERACTIONS: dict[str, dict[str, Any]] = {i["description"]: i for i in _PACT["interactions"]}


def _interaction(description: str) -> dict[str, Any]:
    assert description in _INTERACTIONS, f"Unknown Pact interaction: {description!r}"
    return _INTERACTIONS[description]


# ── App factory ───────────────────────────────────────────────────────────────


def _build_app() -> FastAPI:
    """Full api-gateway app with in-memory stores — provider under test."""
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


# ── Shared fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    return _build_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Provider state helpers ────────────────────────────────────────────────────


async def _seed_request(
    app: FastAPI, *, status: str = "queued", result: dict[str, Any] | None = None
) -> str:
    """Directly write a RequestState into the in-memory store, bypassing the API."""
    from src.agents.request_store import RequestState

    request_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    state = RequestState(
        request_id=request_id,
        status=status,
        created_at=now,
        updated_at=now,
        result=result,
    )
    await app.state.request_store.save(state)
    return request_id


async def _seed_hitl_request(app: FastAPI) -> str:
    """Directly write a HITLRequest into the gateway's in-memory store."""
    from src.agents.hitl_gateway import HITLRequest

    request_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    req = HITLRequest(
        request_id=request_id,
        agent_id="test-agent-00000000",
        action_type="write_file",
        action_parameters={"path": "/tmp/report.txt"},
        risk_score=0.85,
        context_summary="Agent proposes writing a quarterly report file.",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    await app.state.hitl_gateway._store.save(req)
    return request_id


# ── Pact metadata verification ────────────────────────────────────────────────


@pytest.mark.unit
class TestPactMetadataVerification:
    """Verify that the provider's identity matches the Pact file."""

    def test_pact_consumer_is_frontend(self) -> None:
        assert _PACT["consumer"]["name"] == "frontend"

    def test_pact_provider_is_api_gateway(self) -> None:
        assert _PACT["provider"]["name"] == "api-gateway"

    def test_all_interactions_have_provider_tests(self) -> None:
        """Every Pact interaction must have a corresponding provider test class.

        This test documents the coverage contract: if a new interaction is added
        to the Pact file without a provider test, this assertion will fail and
        alert the team.
        """
        covered = {
            "a POST /v1/requests to submit a domain request",
            "a POST /v1/requests with an empty request_text",
            "a GET /v1/requests/{id} for a queued request",
            "a GET /v1/requests/{id} for a completed request",
            "a GET /v1/requests/{id} for an unknown request_id",
            "a GET /v1/hitl/status when the gateway is operational",
            "a POST /v1/hitl/requests/{id}/decision with APPROVED",
            "a POST /v1/hitl/requests/{id}/decision with REJECTED",
            "a POST /v1/hitl/requests/{id}/decision for an unknown or expired request",
        }
        pact_descriptions = {i["description"] for i in _PACT["interactions"]}
        missing = pact_descriptions - covered
        assert not missing, (
            f"Pact interactions without provider tests: {missing!r}\n"
            "Add a provider test class for each uncovered interaction."
        )


# ── Interaction: POST /v1/requests (valid) ────────────────────────────────────


@pytest.mark.unit
class TestProviderSubmitRequestValid:
    """Pact interaction: 'a POST /v1/requests to submit a domain request'."""

    async def test_status_is_202(self, client: AsyncClient) -> None:
        interaction = _interaction("a POST /v1/requests to submit a domain request")
        contracted_body = interaction["request"]["body"]

        response = await client.post(
            "/v1/requests",
            json=contracted_body,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 202

    async def test_response_has_content_type_json(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/requests",
            json={"request_text": "Process this task", "priority": "normal"},
        )
        assert "application/json" in response.headers.get("content-type", "")

    async def test_response_body_has_all_contracted_fields(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/requests",
            json={"request_text": "Process this task", "priority": "normal"},
        )
        body = response.json()
        for field in ("request_id", "status", "created_at", "message"):
            assert field in body, f"Missing contracted field: {field!r}"

    async def test_request_id_is_uuid_format(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/requests",
            json={"request_text": "Process this task", "priority": "normal"},
        )
        rid = response.json()["request_id"]
        # Pact matchingRule: type — must be a non-empty string; verify UUID shape
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            rid,
        ), f"request_id {rid!r} is not a valid UUID v4"

    async def test_status_field_is_queued(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/requests",
            json={"request_text": "Process this task", "priority": "normal"},
        )
        # Pact matchingRule: regex ^queued$
        assert response.json()["status"] == "queued"


# ── Interaction: POST /v1/requests (validation error) ────────────────────────


@pytest.mark.unit
class TestProviderSubmitRequestValidationError:
    """Pact interaction: 'a POST /v1/requests with an empty request_text'."""

    async def test_status_is_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/requests",
            json={"request_text": "", "priority": "normal"},
        )
        assert response.status_code == 422

    async def test_response_has_detail_field(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/requests",
            json={"request_text": "", "priority": "normal"},
        )
        assert "detail" in response.json()


# ── Interaction: GET /v1/requests/{id} (queued) ───────────────────────────────


@pytest.mark.unit
class TestProviderGetRequestQueued:
    """Pact interaction: 'a GET /v1/requests/{id} for a queued request'."""

    async def test_status_is_200(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_request(app, status="queued")
        response = await client.get(f"/v1/requests/{request_id}")
        assert response.status_code == 200

    async def test_response_has_all_contracted_fields(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        request_id = await _seed_request(app, status="queued")
        body = (await client.get(f"/v1/requests/{request_id}")).json()
        for field in (
            "request_id",
            "status",
            "created_at",
            "updated_at",
            "result",
            "error",
            "message",
        ):
            assert field in body, f"Missing contracted field: {field!r}"

    async def test_status_is_in_contracted_enum(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_request(app, status="queued")
        body = (await client.get(f"/v1/requests/{request_id}")).json()
        # Pact matchingRule: regex ^(queued|processing|completed|failed)$
        assert body["status"] in {"queued", "processing", "completed", "failed"}

    async def test_request_id_matches_path(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_request(app, status="queued")
        body = (await client.get(f"/v1/requests/{request_id}")).json()
        assert body["request_id"] == request_id


# ── Interaction: GET /v1/requests/{id} (completed) ───────────────────────────


@pytest.mark.unit
class TestProviderGetRequestCompleted:
    """Pact interaction: 'a GET /v1/requests/{id} for a completed request'."""

    async def test_status_is_200(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_request(
            app,
            status="completed",
            result={"summary": "Task completed successfully."},
        )
        response = await client.get(f"/v1/requests/{request_id}")
        assert response.status_code == 200

    async def test_status_field_is_completed(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_request(app, status="completed", result={"ok": True})
        body = (await client.get(f"/v1/requests/{request_id}")).json()
        assert body["status"] == "completed"

    async def test_result_field_is_present_and_non_null(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        result_data = {"summary": "Task completed successfully."}
        request_id = await _seed_request(app, status="completed", result=result_data)
        body = (await client.get(f"/v1/requests/{request_id}")).json()
        # Pact matchingRule: type — result must be non-null for a completed request
        assert body["result"] is not None


# ── Interaction: GET /v1/requests/{id} (not found) ───────────────────────────


@pytest.mark.unit
class TestProviderGetRequestNotFound:
    """Pact interaction: 'a GET /v1/requests/{id} for an unknown request_id'."""

    async def test_status_is_404(self, client: AsyncClient) -> None:
        response = await client.get("/v1/requests/00000000-0000-0000-0000-000000000099")
        assert response.status_code == 404

    async def test_response_has_detail_field(self, client: AsyncClient) -> None:
        body = (await client.get("/v1/requests/00000000-0000-0000-0000-000000000099")).json()
        assert "detail" in body


# ── Interaction: GET /v1/hitl/status ─────────────────────────────────────────


@pytest.mark.unit
class TestProviderHITLStatus:
    """Pact interaction: 'a GET /v1/hitl/status when the gateway is operational'."""

    async def test_status_is_200(self, client: AsyncClient) -> None:
        response = await client.get("/v1/hitl/status")
        assert response.status_code == 200

    async def test_status_field_is_operational(self, client: AsyncClient) -> None:
        body = (await client.get("/v1/hitl/status")).json()
        # Pact matchingRule: regex ^operational$
        assert body["status"] == "operational"

    async def test_pending_count_is_integer(self, client: AsyncClient) -> None:
        body = (await client.get("/v1/hitl/status")).json()
        # Pact matchingRule: integer
        assert isinstance(body["pending_count"], int)
        assert body["pending_count"] >= 0

    async def test_message_field_is_present(self, client: AsyncClient) -> None:
        body = (await client.get("/v1/hitl/status")).json()
        assert isinstance(body["message"], str)
        assert len(body["message"]) > 0


# ── Interaction: POST /v1/hitl/requests/{id}/decision (APPROVED) ─────────────


@pytest.mark.unit
class TestProviderHITLDecisionApproved:
    """Pact interaction: 'a POST /v1/hitl/requests/{id}/decision with APPROVED'."""

    async def test_status_is_200(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_hitl_request(app)
        response = await client.post(
            f"/v1/hitl/requests/{request_id}/decision",
            json={
                "decision": "APPROVED",
                "rationale": "Action is safe and within approved scope.",
                "approver_id": "operator-001",
            },
        )
        assert response.status_code == 200

    async def test_decision_field_is_approved(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_hitl_request(app)
        body = (
            await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": "Action is safe and within approved scope.",
                    "approver_id": "operator-001",
                },
            )
        ).json()
        # Pact matchingRule: regex ^(APPROVED|REJECTED)$
        assert body["decision"] == "APPROVED"

    async def test_request_id_echoed_in_response(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_hitl_request(app)
        body = (
            await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": "Action is safe and within approved scope.",
                    "approver_id": "operator-001",
                },
            )
        ).json()
        assert body["request_id"] == request_id

    async def test_response_has_all_contracted_fields(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        request_id = await _seed_hitl_request(app)
        body = (
            await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": "Action is safe and within approved scope.",
                    "approver_id": "operator-001",
                },
            )
        ).json()
        for field in ("request_id", "decision", "message"):
            assert field in body, f"Missing contracted field: {field!r}"


# ── Interaction: POST /v1/hitl/requests/{id}/decision (REJECTED) ─────────────


@pytest.mark.unit
class TestProviderHITLDecisionRejected:
    """Pact interaction: 'a POST /v1/hitl/requests/{id}/decision with REJECTED'."""

    async def test_status_is_200(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_hitl_request(app)
        response = await client.post(
            f"/v1/hitl/requests/{request_id}/decision",
            json={
                "decision": "REJECTED",
                "rationale": "Action exceeds approved risk threshold for this environment.",
                "approver_id": "operator-001",
            },
        )
        assert response.status_code == 200

    async def test_decision_field_is_rejected(self, app: FastAPI, client: AsyncClient) -> None:
        request_id = await _seed_hitl_request(app)
        body = (
            await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "REJECTED",
                    "rationale": "Action exceeds approved risk threshold for this environment.",
                    "approver_id": "operator-001",
                },
            )
        ).json()
        assert body["decision"] == "REJECTED"


# ── Interaction: POST /v1/hitl/requests/{id}/decision (not found) ────────────


@pytest.mark.unit
class TestProviderHITLDecisionNotFound:
    """Pact interaction: 'a POST /v1/hitl/requests/{id}/decision for an unknown or expired request'."""

    async def test_status_is_404(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/hitl/requests/00000000-0000-0000-0000-000000000099/decision",
            json={
                "decision": "APPROVED",
                "rationale": "Attempting to approve an unknown request.",
                "approver_id": "operator-001",
            },
        )
        assert response.status_code == 404

    async def test_response_has_detail_field(self, client: AsyncClient) -> None:
        body = (
            await client.post(
                "/v1/hitl/requests/00000000-0000-0000-0000-000000000099/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": "Attempting to approve an unknown request.",
                    "approver_id": "operator-001",
                },
            )
        ).json()
        assert "detail" in body
