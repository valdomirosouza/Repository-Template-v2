"""Integration tests for RedisIdempotencyStore using fakeredis (no external service required).

Exercises the atomic SET-NX claim, the existing-key replay path, and release (SPEC-API-002 / ADR-0077).
"""

from __future__ import annotations

from datetime import UTC, datetime

import fakeredis
import pytest

from src.agents.idempotency_store import IdempotencyRecord, RedisIdempotencyStore

pytestmark = pytest.mark.integration


@pytest.fixture
async def redis_client():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def store(redis_client) -> RedisIdempotencyStore:
    return RedisIdempotencyStore(client=redis_client)


def _rec(rid: str, fp: str = "fp") -> IdempotencyRecord:
    return IdempotencyRecord(request_id=rid, fingerprint=fp, created_at=datetime.now(UTC))


async def test_first_claim_wins_second_sees_winner(store: RedisIdempotencyStore) -> None:
    got_a, created_a = await store.claim("k1", _rec("id-a"))
    assert created_a is True and got_a.request_id == "id-a"

    got_b, created_b = await store.claim("k1", _rec("id-b"))
    assert created_b is False
    assert got_b.request_id == "id-a"  # the persisted winner, not the new attempt
    assert got_b.fingerprint == "fp"


async def test_release_allows_reclaim(store: RedisIdempotencyStore) -> None:
    await store.claim("k2", _rec("id-a"))
    await store.release("k2")
    _, created = await store.claim("k2", _rec("id-b"))
    assert created is True  # key was released, so the new attempt wins


async def test_claim_sets_a_ttl(store: RedisIdempotencyStore, redis_client) -> None:
    await store.claim("k3", _rec("id-a"))
    ttl = await redis_client.ttl(store._key("k3"))
    assert ttl > 0  # SET NX EX applied a positive expiry (no unbounded growth)
