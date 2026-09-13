"""Unit tests for the W12-T3 wiring primitives: llm_factory, InMemoryBroker subscriptions,
and the request-store HITL link index (issues #356 / #355).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.agents.llm_factory import build_llm_client, unwrap_stack
from src.agents.request_store import InMemoryRequestStore, RedisRequestStore, RequestState
from src.shared.broker import InMemoryBroker
from src.shared.config import settings
from src.shared.llm_client import StubLLMClient

pytestmark = pytest.mark.unit


# ── factory ──────────────────────────────────────────────────────────────────


def test_factory_builds_the_documented_stack_over_an_injected_base():
    client = build_llm_client(StubLLMClient())
    assert unwrap_stack(client) == [
        "OtelLLMClientWrapper",
        "ResilientLLMClientWrapper",
        "TimeoutLLMClientWrapper",
        "StubLLMClient",
    ]


def test_factory_applies_resilience_settings(monkeypatch: pytest.MonkeyPatch):
    """The settings were dead config before W12-T3; prove they reach the wrappers."""
    monkeypatch.setattr(settings, "llm_call_timeout_seconds", 7.5)
    monkeypatch.setattr(settings, "llm_circuit_breaker_threshold", 2)
    client = build_llm_client(StubLLMClient())
    resilient = client._inner  # type: ignore[attr-defined]
    assert resilient._inner._timeout == 7.5
    assert resilient._cb._threshold == 2


async def test_factory_client_completes_through_every_layer():
    client = build_llm_client(StubLLMClient('{"content": "hello"}'))
    assert await client.complete("u", system="s", trace_id="t") == '{"content": "hello"}'


async def test_circuit_breaker_opens_after_threshold(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "llm_circuit_breaker_threshold", 1)
    monkeypatch.setattr(settings, "llm_retry_max_attempts", 1)

    class Boom:
        async def complete(self, user: str, system: str = "", trace_id: str | None = None) -> str:
            raise ConnectionError("connect refused")  # transient keyword → retried, then fails

    client = build_llm_client(Boom())  # type: ignore[arg-type]
    with pytest.raises(Exception):
        await client.complete("u")
    from src.shared.retry import CircuitBreakerError

    with pytest.raises(CircuitBreakerError):
        await client.complete("u")


# ── broker subscriptions ─────────────────────────────────────────────────────


async def test_in_memory_broker_dispatches_to_subscribers_and_isolates_failures():
    broker = InMemoryBroker()
    seen: list[tuple[str, dict[str, Any]]] = []

    async def good(topic: str, payload: dict[str, Any]) -> None:
        seen.append((topic, payload))

    async def bad(topic: str, payload: dict[str, Any]) -> None:
        raise RuntimeError("subscriber bug")

    broker.subscribe("a.b.c", bad)
    broker.subscribe("a.b.c", good)
    await broker.publish("a.b.c", {"x": 1})  # bad must not break good or the publisher
    await broker.publish("other.topic", {"x": 2})
    assert seen == [("a.b.c", {"x": 1})]
    assert [e["topic"] for e in broker.published] == ["a.b.c", "other.topic"]

    broker.unsubscribe("a.b.c", good)
    await broker.publish("a.b.c", {"x": 3})
    assert len(seen) == 1


# ── request-store HITL link ─────────────────────────────────────────────────


def _waiting(request_id: str, hitl_id: str) -> RequestState:
    now = datetime.now(UTC)
    return RequestState(
        request_id=request_id,
        status="waiting_for_human_approval",
        created_at=now,
        updated_at=now,
        result={"status": "waiting_for_human_approval", "hitl_request_id": hitl_id},
    )


async def test_in_memory_store_links_hitl_request_id():
    store = InMemoryRequestStore()
    await store.save(_waiting("req-1", "hitl-1"))
    linked = await store.get_by_hitl_request_id("hitl-1")
    assert linked is not None and linked.request_id == "req-1"
    assert await store.get_by_hitl_request_id("hitl-none") is None


class _FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, Any] = {}

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        self.kv[key] = value

    async def get(self, key: str) -> Any:
        return self.kv.get(key)


async def test_redis_store_writes_and_resolves_hitl_link_key():
    r = _FakeRedis()
    store = RedisRequestStore(client=r)
    await store.save(_waiting("req-2", "hitl-2"))
    assert any(k.endswith(":hitl_link:hitl-2") for k in r.kv)
    linked = await store.get_by_hitl_request_id("hitl-2")
    assert linked is not None and linked.request_id == "req-2"
    assert await store.get_by_hitl_request_id("hitl-zzz") is None
