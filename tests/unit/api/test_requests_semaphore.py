"""Unit tests for submit_request endpoint — semaphore cap behaviour.

Spec: specs/api/rest-api-design.md (Rate Limiting, Backpressure)
ADR:  ADR-0002 (Technology Stack Selection)
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from src.agents.request_store import InMemoryRequestStore
from src.api.rest.main import app
from src.shared.broker import InMemoryBroker

# ── Helpers ───────────────────────────────────────────────────────────────────


def _wire_dependencies() -> None:
    """Ensure request_store and broker are present in app.state for tests."""
    if not hasattr(app.state, "request_store") or app.state.request_store is None:
        app.state.request_store = InMemoryRequestStore()
    if not hasattr(app.state, "broker") or app.state.broker is None:
        app.state.broker = InMemoryBroker()


def _client_with_semaphore(available_slots: int) -> TestClient:
    """Return a TestClient with the agent semaphore pre-configured."""
    _wire_dependencies()
    app.state.agent_semaphore = asyncio.Semaphore(available_slots)
    # Set remaining slots to 0 if requested
    if available_slots == 0:
        # Acquire all slots so _value == 0
        for _ in range(1):
            app.state.agent_semaphore._value = 0
    return TestClient(app, raise_server_exceptions=False)


# ── Semaphore behaviour ───────────────────────────────────────────────────────


class TestSubmitRequestSemaphore:
    def test_returns_503_when_semaphore_exhausted(self):
        _wire_dependencies()
        app.state.agent_semaphore = asyncio.Semaphore(1)
        app.state.agent_semaphore._value = 0  # simulate all slots taken

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/v1/requests",
            json={"request_text": "synthetic test input", "priority": "normal"},
        )

        assert response.status_code == 503
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "5"

    def test_returns_retry_after_header_on_503(self):
        _wire_dependencies()
        app.state.agent_semaphore = asyncio.Semaphore(1)
        app.state.agent_semaphore._value = 0

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/v1/requests",
            json={"request_text": "synthetic test input", "priority": "normal"},
        )

        assert response.json()["detail"] == "Agent capacity exhausted — retry later"

    def test_returns_202_when_slots_available(self):
        _wire_dependencies()
        app.state.agent_semaphore = asyncio.Semaphore(10)  # plenty of slots

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/v1/requests",
            json={"request_text": "synthetic test input", "priority": "normal"},
        )

        assert response.status_code == 202

    def test_no_semaphore_in_state_still_returns_202(self):
        """Endpoint is backwards-compatible if semaphore not yet initialised."""
        _wire_dependencies()
        if hasattr(app.state, "agent_semaphore"):
            del app.state.agent_semaphore

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/v1/requests",
            json={"request_text": "synthetic test input", "priority": "normal"},
        )

        assert response.status_code == 202
