"""Unit tests for HITLRedisStore — with and without AES-256-GCM encryption.

Spec: specs/privacy/redis-tls.md §4
ADR:  ADR-0019 (Redis TLS and Value Encryption)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from src.agents.hitl_gateway import HITLRequest, HITLStatus
from src.agents.hitl_store import HITLRedisStore
from src.shared.db_encryption import EncryptedField

_TEST_KEY = "b" * 64  # valid 32-byte test key — never use in production


def _make_request(request_id: str = "req-001", agent_id: str = "agent-x") -> HITLRequest:
    now = datetime.now(UTC)
    return HITLRequest(
        request_id=request_id,
        agent_id=agent_id,
        action_type="send_email",
        action_parameters={"to": "team@example.com", "subject": "Weekly summary"},
        risk_score=0.6,
        context_summary="User requested a weekly report [EMAIL] [NAME]",
        created_at=now,
        expires_at=now + timedelta(hours=1),
        status=HITLStatus.PENDING,
    )


@pytest.fixture()
def redis_client() -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture()
def store_plain(redis_client: fakeredis.FakeAsyncRedis) -> HITLRedisStore:
    return HITLRedisStore(client=redis_client)


@pytest.fixture()
def store_encrypted(redis_client: fakeredis.FakeAsyncRedis) -> HITLRedisStore:
    return HITLRedisStore(client=redis_client, encryption=EncryptedField(_TEST_KEY))


class TestHITLRedisStorePlain:
    async def test_save_and_get_roundtrip(self, store_plain: HITLRedisStore) -> None:
        req = _make_request()
        await store_plain.save(req)
        result = await store_plain.get(req.request_id)
        assert result is not None
        assert result.request_id == req.request_id
        assert result.action_type == req.action_type
        assert result.context_summary == req.context_summary

    async def test_get_missing_returns_none(self, store_plain: HITLRedisStore) -> None:
        assert await store_plain.get("nonexistent") is None

    async def test_pending_count(self, store_plain: HITLRedisStore) -> None:
        await store_plain.save(_make_request("r1"))
        await store_plain.save(_make_request("r2"))
        assert await store_plain.pending_count() == 2

    async def test_list_pending_returns_all_pending(self, store_plain: HITLRedisStore) -> None:
        await store_plain.save(_make_request("r1"))
        await store_plain.save(_make_request("r2"))
        pending = await store_plain.list_pending()
        assert {r.request_id for r in pending} == {"r1", "r2"}
        assert all(r.status == HITLStatus.PENDING for r in pending)

    async def test_list_pending_excludes_evicted(self, store_plain: HITLRedisStore) -> None:
        await store_plain.save(_make_request("r1"))
        await store_plain.save(_make_request("r2"))
        await store_plain.evict("r1")
        pending = await store_plain.list_pending()
        assert {r.request_id for r in pending} == {"r2"}

    async def test_evict_removes_from_pending(self, store_plain: HITLRedisStore) -> None:
        req = _make_request()
        await store_plain.save(req)
        await store_plain.evict(req.request_id)
        assert await store_plain.get_active(req.request_id) is None
        assert await store_plain.pending_count() == 0

    async def test_archive_moves_to_expired_key(self, store_plain: HITLRedisStore) -> None:
        req = _make_request()
        await store_plain.save(req)
        req.status = HITLStatus.APPROVED
        await store_plain.archive(req.request_id, req)
        # No longer active
        assert await store_plain.get_active(req.request_id) is None
        # Still retrievable via get()
        archived = await store_plain.get(req.request_id)
        assert archived is not None
        assert archived.status == HITLStatus.APPROVED


class TestHITLRedisStoreEncrypted:
    async def test_save_and_get_roundtrip_with_encryption(
        self, store_encrypted: HITLRedisStore, redis_client: fakeredis.FakeAsyncRedis
    ) -> None:
        req = _make_request()
        await store_encrypted.save(req)
        result = await store_encrypted.get(req.request_id)
        assert result is not None
        assert result.request_id == req.request_id
        assert result.context_summary == req.context_summary
        assert result.action_parameters == req.action_parameters

    async def test_stored_bytes_are_not_plaintext_json(
        self, store_encrypted: HITLRedisStore, redis_client: fakeredis.FakeAsyncRedis
    ) -> None:
        req = _make_request()
        await store_encrypted.save(req)
        # Read the raw value from Redis — should NOT be parseable as JSON
        raw = await redis_client.get(f"hitl:req:{req.request_id}")
        assert raw is not None
        with pytest.raises((json.JSONDecodeError, UnicodeDecodeError, ValueError)):
            json.loads(raw)

    async def test_encrypted_value_starts_with_prefix(
        self, store_encrypted: HITLRedisStore, redis_client: fakeredis.FakeAsyncRedis
    ) -> None:
        req = _make_request()
        await store_encrypted.save(req)
        raw = await redis_client.get(f"hitl:req:{req.request_id}")
        assert raw is not None
        assert raw.startswith("enc:v1:")

    async def test_pending_count_works_with_encryption(
        self, store_encrypted: HITLRedisStore
    ) -> None:
        await store_encrypted.save(_make_request("r1"))
        await store_encrypted.save(_make_request("r2"))
        assert await store_encrypted.pending_count() == 2

    async def test_archive_roundtrip_with_encryption(self, store_encrypted: HITLRedisStore) -> None:
        req = _make_request()
        await store_encrypted.save(req)
        req.status = HITLStatus.REJECTED
        await store_encrypted.archive(req.request_id, req)
        archived = await store_encrypted.get(req.request_id)
        assert archived is not None
        assert archived.status == HITLStatus.REJECTED

    async def test_plaintext_passthrough_for_unencrypted_rows(
        self, store_encrypted: HITLRedisStore, redis_client: fakeredis.FakeAsyncRedis
    ) -> None:
        # Simulate a row written before encryption was enabled (plaintext JSON)
        req = _make_request("legacy-row")
        plain_json = HITLRedisStore._serialize(req)
        await redis_client.set(f"hitl:req:{req.request_id}", plain_json)
        # The encrypted store must still read it via the passthrough path
        result = await store_encrypted.get(req.request_id)
        assert result is not None
        assert result.request_id == "legacy-row"
