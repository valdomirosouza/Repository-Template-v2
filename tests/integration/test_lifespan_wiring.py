"""Lifespan wiring test — documented capabilities are reachable at runtime (W12-T1, #354).

ADR-0089 makes it an invariant: a capability that CLAUDE.md, an ADR or a spec describes must be
constructed by the application lifespan (or the docs must say it is not wired). The Seven-Axis
Review (2026-09-12) found five documented capabilities the running service never reached:
harness modes, the resilient/OTel LLM stack, HTTP Golden Signals, an approval-event consumer,
and the agent semaphore. This test was written red first and turned green by W12-T2…T6.

Offline by construction: every infra client is forced to fail fast so the lifespan takes the
in-memory fallbacks (that is the documented behaviour, CLAUDE.md §0.1). The LLM base client is a
stub, but it is wrapped by the *real* production stack.

Spec: specs/system/architecture.md §Runtime wiring invariants · ADR-0089
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.shared.config import settings
from src.shared.llm_client import StubLLMClient

pytestmark = pytest.mark.integration


class _DeadRedis:
    async def ping(self) -> None:
        raise ConnectionError("redis unreachable (test)")


async def _fail_pool(*_: Any, **__: Any) -> None:
    raise ConnectionError("postgres unreachable (test)")


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every infrastructure fallback and a stub LLM base, keep AI agents enabled."""
    import src.api.rest.main as main

    monkeypatch.setattr(main, "setup_telemetry", lambda *a, **k: None)  # no OTLP exporter noise
    monkeypatch.setattr(main.asyncpg, "create_pool", _fail_pool)
    monkeypatch.setattr(main.redis_async, "from_url", lambda *a, **k: _DeadRedis())

    from src.shared import broker as broker_mod

    async def _fail_start(self: Any) -> None:
        raise ConnectionError("kafka unreachable (test)")

    monkeypatch.setattr(broker_mod.KafkaEventBroker, "start", _fail_start)

    import src.agents.llm_factory as factory

    real_build = factory.build_llm_client
    monkeypatch.setattr(factory, "build_llm_client", lambda base=None: real_build(StubLLMClient()))

    monkeypatch.setattr(settings, "ai_agents_enabled", True)
    monkeypatch.setattr(settings, "shutdown_drain_seconds", 0)
    monkeypatch.setattr(settings, "hitl_expiry_sweep_seconds", 1)
    monkeypatch.setattr(settings, "kafka_consumer_retry_backoff_seconds", 0.01)


@pytest.fixture
async def booted(offline: None) -> AsyncIterator[Any]:
    from src.api.rest.main import app, lifespan

    async with lifespan(app):
        await asyncio.sleep(0.05)  # let the consumer tasks subscribe
        yield app


# ── ADR-0089 invariants ────────────────────────────────────────────────────────


async def test_fallbacks_are_the_in_memory_implementations(booted: Any) -> None:
    from src.agents.hitl_store import InMemoryHITLStore
    from src.agents.request_store import InMemoryRequestStore
    from src.shared.broker import InMemoryBroker

    assert isinstance(booted.state.broker, InMemoryBroker)
    assert isinstance(booted.state.request_store, InMemoryRequestStore)
    assert isinstance(booted.state.hitl_gateway._store, InMemoryHITLStore)
    assert booted.state.ai_agents_active is True


async def test_llm_client_is_the_documented_wrapper_stack(booted: Any) -> None:
    """ADR-0044/0045/0075: Otel → Resilient → Timeout → provider. Not a bare client."""
    from src.agents.llm_factory import unwrap_stack

    stack = unwrap_stack(booted.state.llm_client)
    assert stack[:3] == [
        "OtelLLMClientWrapper",
        "ResilientLLMClientWrapper",
        "TimeoutLLMClientWrapper",
    ], stack
    assert stack[-1] == "StubLLMClient"  # the injected base for this test
    # and the consumer uses that same instance, not a private bare AnthropicLLMClient
    assert booted.state.request_consumer._llm is booted.state.llm_client


async def test_http_golden_signals_middleware_is_installed(booted: Any) -> None:
    from src.api.rest.middleware.golden_signals import GoldenSignalsMiddleware
    from src.observability.metrics import REQUEST_COUNTER

    assert any(m.cls is GoldenSignalsMiddleware for m in booted.user_middleware)
    before = REQUEST_COUNTER.labels(settings.service_name, "GET", "/health", "200")._value.get()
    async with AsyncClient(transport=ASGITransport(app=booted), base_url="http://t") as client:
        assert (await client.get("/health")).status_code == 200
    after = REQUEST_COUNTER.labels(settings.service_name, "GET", "/health", "200")._value.get()
    assert after == before + 1  # http_requests_total is actually populated (FEAT-001)


async def test_approval_consumer_and_expiry_sweeper_are_running(booted: Any) -> None:
    from src.workers.approval_consumer import TOPICS

    assert not booted.state.approval_consumer_task.done()
    assert not booted.state.hitl_sweeper_task.done()
    subs = booted.state.broker._subscribers
    assert all(topic in subs and subs[topic] for topic in TOPICS)
    assert "domain.request.created" in subs  # request consumer, in-memory transport


async def test_semaphore_is_acquired_around_agent_runs(booted: Any) -> None:
    """The capacity gate reads this semaphore; before W12 nothing ever acquired it."""
    consumer = booted.state.request_consumer
    assert consumer._semaphore is booted.state.agent_semaphore

    seen: list[int] = []
    sem = booted.state.agent_semaphore

    async def _spy(*_: Any, **__: Any) -> dict[str, Any]:
        seen.append(sem._value)
        return {"status": "completed", "outcome": "noop"}

    orchestrator = consumer._build_orchestrator()
    orchestrator.run = _spy  # type: ignore[method-assign]
    consumer._build_orchestrator = lambda: orchestrator  # type: ignore[method-assign]
    await consumer._process({"payload": {"request_id": "req-sem-1", "request_text": "x"}})
    assert seen == [settings.max_concurrent_agents - 1]


async def test_submitted_request_is_processed_end_to_end_in_memory(booted: Any) -> None:
    """POST → in-memory broker → request consumer → orchestrator: status leaves `queued`."""
    async with AsyncClient(transport=ASGITransport(app=booted), base_url="http://t") as client:
        res = await client.post("/v1/requests", json={"request_text": "summarise the runbook"})
        assert res.status_code == 202, res.text
        request_id = res.json()["request_id"]
        for _ in range(50):
            await asyncio.sleep(0.02)
            state = await booted.state.request_store.get(request_id)
            if state is not None and state.status not in {"queued", "processing"}:
                break
    assert state is not None
    assert state.status in {"completed", "waiting_for_human_approval", "failed"}, state
    assert state.status != "queued"


async def test_waiting_for_approval_is_stored_honestly(booted: Any) -> None:
    """A HITL suspension must not be written as `completed` (the open-loop bug)."""
    consumer = booted.state.request_consumer

    async def _suspend(*_: Any, **__: Any) -> dict[str, Any]:
        return {"status": "waiting_for_human_approval", "hitl_request_id": "hitl-abc"}

    orchestrator = consumer._build_orchestrator()
    orchestrator.run = _suspend  # type: ignore[method-assign]
    consumer._build_orchestrator = lambda: orchestrator  # type: ignore[method-assign]
    await consumer._process({"payload": {"request_id": "req-wait-1", "request_text": "x"}})
    state = await booted.state.request_store.get("req-wait-1")
    assert state is not None and state.status == "waiting_for_human_approval"
    linked = await booted.state.request_store.get_by_hitl_request_id("hitl-abc")
    assert linked is not None and linked.request_id == "req-wait-1"


async def test_harness_coordinator_is_constructed_when_mode_is_not_solo(
    offline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLAUDE.md §0.1 Harness Modes: simplified/full must reach HarnessCoordinator."""
    monkeypatch.setattr(settings, "harness_mode", "simplified")
    from src.agents.harness.coordinator import HarnessCoordinator
    from src.api.rest.main import app, lifespan

    async with lifespan(app):
        assert isinstance(app.state.harness, HarnessCoordinator)
        assert app.state.request_consumer._harness is app.state.harness


async def test_agents_disabled_starts_no_consumers(
    offline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ai_agents_enabled=false` must actually disable the extension, not just config checks."""
    monkeypatch.setattr(settings, "ai_agents_enabled", False)
    from src.api.rest.main import app, lifespan

    async with lifespan(app):
        assert app.state.ai_agents_active is False
        assert getattr(app.state, "consumer_task", None) is None or app.state.consumer_task.done()
