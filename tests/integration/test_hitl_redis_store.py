"""Integration tests for HITLRedisStore using fakeredis (no external service required).

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)

All test inputs use clearly synthetic, obviously fake data.
No real personal data appears in this file.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from src.agents.hitl_gateway import HITLRequest, HITLStatus
from src.agents.hitl_store import HITLRedisStore

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def redis_client():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def store(redis_client):
    return HITLRedisStore(client=redis_client)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_request(
    agent_id: str = "agent-test",
    expires_in: timedelta = timedelta(hours=1),
) -> HITLRequest:
    now = datetime.now(UTC)
    return HITLRequest(
        request_id=str(uuid.uuid4()),
        agent_id=agent_id,
        action_type="test_action",
        action_parameters={"key": "synthetic-value"},
        risk_score=0.8,
        context_summary="synthetic context — no real PII",
        created_at=now,
        expires_at=now + expires_in,
    )


# ── Save / Get round-trip ─────────────────────────────────────────────────────


class TestHITLRedisStoreSaveGet:
    @pytest.mark.integration
    async def test_save_get_roundtrip(self, store):
        req = _make_request()
        await store.save(req)
        retrieved = await store.get(req.request_id)
        assert retrieved is not None
        assert retrieved.request_id == req.request_id
        assert retrieved.agent_id == req.agent_id
        assert retrieved.action_type == req.action_type
        assert retrieved.status == HITLStatus.PENDING

    @pytest.mark.integration
    async def test_get_active_returns_pending_request(self, store):
        req = _make_request()
        await store.save(req)
        retrieved = await store.get_active(req.request_id)
        assert retrieved is not None
        assert retrieved.request_id == req.request_id

    @pytest.mark.integration
    async def test_get_returns_none_for_unknown_id(self, store):
        assert await store.get("00000000-0000-0000-0000-000000000000") is None

    @pytest.mark.integration
    async def test_get_active_returns_none_for_unknown_id(self, store):
        assert await store.get_active("00000000-0000-0000-0000-000000000000") is None

    @pytest.mark.integration
    async def test_pending_count_reflects_saves(self, store):
        assert await store.pending_count() == 0
        req1 = _make_request(agent_id="agent-1")
        req2 = _make_request(agent_id="agent-2")
        await store.save(req1)
        await store.save(req2)
        assert await store.pending_count() == 2

    @pytest.mark.integration
    async def test_action_parameters_roundtrip(self, store):
        req = _make_request()
        req.action_parameters = {"nested": {"list": [1, 2, 3]}, "flag": True}
        await store.save(req)
        retrieved = await store.get(req.request_id)
        assert retrieved is not None
        assert retrieved.action_parameters == req.action_parameters


# ── Eviction / archive ────────────────────────────────────────────────────────


class TestHITLRedisStoreEviction:
    @pytest.mark.integration
    async def test_evict_removes_from_active(self, store):
        req = _make_request()
        await store.save(req)
        await store.evict(req.request_id)
        assert await store.get_active(req.request_id) is None
        assert await store.pending_count() == 0

    @pytest.mark.integration
    async def test_evict_nonexistent_is_noop(self, store):
        await store.evict("00000000-0000-0000-0000-000000000000")  # must not raise

    @pytest.mark.integration
    async def test_archive_removes_from_active(self, store):
        req = _make_request()
        req.status = HITLStatus.EXPIRED
        await store.save(req)
        await store.archive(req.request_id, req)
        assert await store.get_active(req.request_id) is None

    @pytest.mark.integration
    async def test_archive_makes_retrievable_via_get(self, store):
        req = _make_request()
        req.status = HITLStatus.EXPIRED
        await store.save(req)
        await store.archive(req.request_id, req)
        retrieved = await store.get(req.request_id)
        assert retrieved is not None
        assert retrieved.status == HITLStatus.EXPIRED

    @pytest.mark.integration
    async def test_archive_decrements_pending_count(self, store):
        req = _make_request()
        await store.save(req)
        assert await store.pending_count() == 1
        await store.archive(req.request_id, req)
        assert await store.pending_count() == 0


# ── Expired pending requests ──────────────────────────────────────────────────


class TestHITLRedisStorePendingExpired:
    @pytest.mark.integration
    async def test_get_pending_expired_returns_past_deadline(self, store):
        now = datetime.now(UTC)
        expired_req = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="agent-x",
            action_type="act",
            action_parameters={},
            risk_score=0.5,
            context_summary="synthetic ctx",
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),  # already expired
        )
        valid_req = _make_request()  # expires in 1h
        await store.save(expired_req)
        await store.save(valid_req)

        expired = await store.get_pending_expired(now)
        ids = [r.request_id for r in expired]
        assert expired_req.request_id in ids
        assert valid_req.request_id not in ids

    @pytest.mark.integration
    async def test_get_pending_expired_returns_empty_when_none_expired(self, store):
        req = _make_request()  # expires in 1h
        await store.save(req)
        now = datetime.now(UTC)
        expired = await store.get_pending_expired(now)
        assert expired == []

    @pytest.mark.integration
    async def test_get_pending_expired_skips_non_pending_status(self, store):
        now = datetime.now(UTC)
        req = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="agent-y",
            action_type="act",
            action_parameters={},
            risk_score=0.5,
            context_summary="synthetic ctx",
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
            status=HITLStatus.APPROVED,  # already decided — should not appear as expired pending
        )
        await store.save(req)
        expired = await store.get_pending_expired(now)
        assert all(r.request_id != req.request_id for r in expired)
