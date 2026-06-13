"""Lightweight chaos smoke — single-fault resilience checks that gate PRs (W2-10).

Fast, in-process, deterministic fault injection (no Docker/k8s) so chaos can gate a PR touching the
resilience-critical paths (src/workers/, src/agents/hitl_*, src/shared/retry.py). The heavier
Chaos-Toolkit experiments (ADR-0075) run against a deployed staging stack, not here.

Run: uv run pytest tests/chaos/test_resilience_smoke.py -m chaos
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from src.shared.retry import TransientError, with_retry

pytestmark = pytest.mark.chaos


@pytest.fixture
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch asyncio.sleep so retry backoff does not slow the smoke."""

    async def _instant(_seconds: float, *_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


class TestRetryResilience:
    """src/shared/retry.py — recover from transient faults, fail-closed when persistent."""

    @pytest.mark.asyncio
    async def test_recovers_from_transient_fault(self, _no_sleep: None) -> None:
        calls = {"n": 0}

        @with_retry(max_attempts=3, min_wait=0.0, max_wait=0.0)
        async def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 2:
                raise TransientError("simulated transient outage")
            return "ok"

        assert await flaky() == "ok"
        assert calls["n"] == 2  # failed once, then recovered

    @pytest.mark.asyncio
    async def test_fails_closed_after_exhausting_attempts(self, _no_sleep: None) -> None:
        @with_retry(max_attempts=2, min_wait=0.0, max_wait=0.0)
        async def always_down() -> str:
            raise TransientError("persistent outage")

        with pytest.raises(TransientError):
            await always_down()


class TestInMemoryDegradeOpen:
    """The request pipeline degrades open: it serves with in-memory infra (Redis/Kafka down)."""

    @pytest.mark.asyncio
    async def test_request_accepted_with_in_memory_store_and_broker(self) -> None:
        from fastapi import FastAPI

        from src.agents.request_store import InMemoryRequestStore
        from src.api.rest.routers.requests import router
        from src.shared.broker import InMemoryBroker

        app = FastAPI()
        app.include_router(router, prefix="/v1")
        app.state.request_store = InMemoryRequestStore()  # Redis-down fallback
        app.state.broker = InMemoryBroker()  # Kafka-down fallback

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/requests", json={"request_text": "chaos smoke probe"})

        assert resp.status_code == 202
        assert resp.json()["status"] == "queued"
