"""Idempotency-key store — in-memory (tests/local) and Redis (production).

Atomically claims an ``Idempotency-Key`` so a retried POST de-duplicates to the original request
instead of creating a duplicate. Mirrors the request/HITL store pattern and degrades open to
in-memory when Redis is down (ADR-0075).

Spec: specs/api/SPEC-API-002-idempotency-keys.md
ADR:  ADR-0077 (idempotency keys), ADR-0009 (caching), ADR-0075 (degrade-open)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from src.shared.config import settings


@dataclass
class IdempotencyRecord:
    """What we store per key: the original request id and a fingerprint of its (masked) body."""

    request_id: str
    fingerprint: str
    created_at: datetime


def fingerprint_body(masked_body: dict[str, Any]) -> str:
    """Salted sha256 of the masked request body — detects 'same key, different body' (NFR-04)."""
    payload = settings.idempotency_fingerprint_salt + json.dumps(masked_body, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IdempotencyStoreProtocol(Protocol):
    """Persistence contract for idempotency keys."""

    async def claim(self, key: str, record: IdempotencyRecord) -> tuple[IdempotencyRecord, bool]:
        """Atomically claim ``key``.

        Returns ``(stored_record, created)``: ``created`` is True when this call won the claim and
        ``stored_record`` is ``record``; False when the key already existed and ``stored_record`` is
        the pre-existing one (the winner's).
        """
        ...

    async def release(self, key: str) -> None:
        """Best-effort release of a just-made claim (when the request is rejected post-claim)."""
        ...


class InMemoryIdempotencyStore:
    """Dict-backed store for tests and local dev without Redis (per-process)."""

    def __init__(self) -> None:
        self._data: dict[str, IdempotencyRecord] = {}

    async def claim(self, key: str, record: IdempotencyRecord) -> tuple[IdempotencyRecord, bool]:
        existing = self._data.get(key)
        if existing is not None:
            return existing, False
        self._data[key] = record
        return record, True

    async def release(self, key: str) -> None:
        self._data.pop(key, None)


class RedisIdempotencyStore:
    """Redis-backed store using SET NX for an atomic cross-instance claim."""

    def __init__(self, client: Any) -> None:
        self._r = client

    def _key(self, key: str) -> str:
        return f"{settings.idempotency_redis_key_prefix}:key:{key}"

    @staticmethod
    def _encode(record: IdempotencyRecord) -> str:
        return json.dumps(
            {
                "request_id": record.request_id,
                "fingerprint": record.fingerprint,
                "created_at": record.created_at.isoformat(),
            }
        )

    @staticmethod
    def _decode(raw: str) -> IdempotencyRecord:
        d = json.loads(raw)
        return IdempotencyRecord(
            request_id=d["request_id"],
            fingerprint=d["fingerprint"],
            created_at=datetime.fromisoformat(d["created_at"]),
        )

    async def claim(self, key: str, record: IdempotencyRecord) -> tuple[IdempotencyRecord, bool]:
        ttl = settings.idempotency_ttl_hours * 3600
        # SET NX EX: claim atomically. `ok` is truthy only when this call created the key.
        ok = await self._r.set(self._key(key), self._encode(record), nx=True, ex=ttl)
        if ok:
            return record, True
        raw = await self._r.get(self._key(key))
        if raw is None:  # rare race: key expired between SET NX and GET — treat as freshly claimed
            await self._r.set(self._key(key), self._encode(record), ex=ttl)
            return record, True
        return self._decode(raw), False

    async def release(self, key: str) -> None:
        await self._r.delete(self._key(key))
