"""Unit tests for InMemoryRequestStore and RedisRequestStore.

Spec: specs/system/request-pipeline.md
ADR:  ADR-0009 (Caching Strategy)

All test inputs use clearly synthetic, obviously fake data.
"""

from __future__ import annotations

from datetime import UTC, datetime

import fakeredis
import pytest

from src.agents.request_store import InMemoryRequestStore, RedisRequestStore, RequestState

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_state(
    request_id: str = "req-001",
    status: str = "queued",
) -> RequestState:
    now = datetime.now(UTC)
    return RequestState(
        request_id=request_id,
        status=status,
        created_at=now,
        updated_at=now,
    )


# ── InMemoryRequestStore ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_and_get_returns_state() -> None:
    store = InMemoryRequestStore()
    state = _make_state()
    await store.save(state)
    retrieved = await store.get(state.request_id)
    assert retrieved is not None
    assert retrieved.status == "queued"
    assert retrieved.request_id == state.request_id


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_id() -> None:
    store = InMemoryRequestStore()
    assert await store.get("does-not-exist") is None


@pytest.mark.asyncio
async def test_status_update_overwrites_previous() -> None:
    store = InMemoryRequestStore()
    state = _make_state(status="queued")
    await store.save(state)
    state.status = "completed"
    await store.save(state)
    retrieved = await store.get(state.request_id)
    assert retrieved is not None
    assert retrieved.status == "completed"


@pytest.mark.asyncio
async def test_result_and_error_persisted() -> None:
    store = InMemoryRequestStore()
    now = datetime.now(UTC)
    state = RequestState(
        request_id="req-002",
        status="completed",
        created_at=now,
        updated_at=now,
        result={"output": "summary text"},
        error=None,
    )
    await store.save(state)
    retrieved = await store.get("req-002")
    assert retrieved is not None
    assert retrieved.result == {"output": "summary text"}
    assert retrieved.error is None


# ── RedisRequestStore ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_store_save_and_get() -> None:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    store = RedisRequestStore(client=client)
    now = datetime.now(UTC)
    state = RequestState(
        request_id="req-redis-001",
        status="processing",
        created_at=now,
        updated_at=now,
        result=None,
        error=None,
    )
    await store.save(state)
    retrieved = await store.get("req-redis-001")
    assert retrieved is not None
    assert retrieved.status == "processing"
    assert retrieved.request_id == "req-redis-001"
    await client.aclose()
