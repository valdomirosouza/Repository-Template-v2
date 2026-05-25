"""HITL request persistence backends.

Implements InMemoryHITLStore (default, non-durable) and HITLRedisStore (production,
survives pod restarts). Both satisfy the HITLStore Protocol defined in hitl_gateway.py.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from src.agents.hitl_gateway import HITLRequest, HITLStatus
from src.shared.config import settings


class InMemoryHITLStore:
    """In-process HITL store. Not durable — requests are lost on pod restart."""

    def __init__(self) -> None:
        self._active: dict[str, HITLRequest] = {}
        self._archived: dict[str, HITLRequest] = {}

    async def save(self, request: HITLRequest) -> None:
        self._active[request.request_id] = request

    async def get(self, request_id: str) -> HITLRequest | None:
        return self._active.get(request_id) or self._archived.get(request_id)

    async def get_active(self, request_id: str) -> HITLRequest | None:
        return self._active.get(request_id)

    async def pending_count(self) -> int:
        return len(self._active)

    async def get_pending_expired(self, now: datetime) -> list[HITLRequest]:
        return [
            req
            for req in self._active.values()
            if req.status == HITLStatus.PENDING and now >= req.expires_at
        ]

    async def evict(self, request_id: str) -> None:
        self._active.pop(request_id, None)

    async def archive(self, request_id: str, request: HITLRequest) -> None:
        self._active.pop(request_id, None)
        self._archived[request_id] = request


class HITLRedisStore:
    """Redis-backed HITL store — survives pod restarts.

    Schema:
      {prefix}:req:{id}      → JSON string; TTL = expires_at + grace_hours
      {prefix}:pending       → Sorted Set; score = expires_at.timestamp()
      {prefix}:expired:{id}  → JSON string; TTL = expired_ttl_days days
    """

    def __init__(self, client: Any) -> None:
        self._r = client
        self._prefix = settings.hitl_redis_key_prefix
        self._grace_hours = settings.hitl_redis_ttl_grace_hours
        self._expired_days = settings.hitl_expired_ttl_days

    # ── Key helpers ───────────────────────────────────────────────────────────

    def _req_key(self, request_id: str) -> str:
        return f"{self._prefix}:req:{request_id}"

    def _expired_key(self, request_id: str) -> str:
        return f"{self._prefix}:expired:{request_id}"

    @property
    def _pending_key(self) -> str:
        return f"{self._prefix}:pending"

    # ── Serialization ─────────────────────────────────────────────────────────

    @staticmethod
    def _serialize(request: HITLRequest) -> str:
        return json.dumps(
            {
                "request_id": request.request_id,
                "agent_id": request.agent_id,
                "action_type": request.action_type,
                "action_parameters": request.action_parameters,
                "risk_score": request.risk_score,
                "context_summary": request.context_summary,
                "created_at": request.created_at.isoformat(),
                "expires_at": request.expires_at.isoformat(),
                "status": request.status.value,
            }
        )

    @staticmethod
    def _deserialize(data: str) -> HITLRequest:
        d = json.loads(data)
        return HITLRequest(
            request_id=d["request_id"],
            agent_id=d["agent_id"],
            action_type=d["action_type"],
            action_parameters=d["action_parameters"],
            risk_score=d["risk_score"],
            context_summary=d["context_summary"],
            created_at=datetime.fromisoformat(d["created_at"]),
            expires_at=datetime.fromisoformat(d["expires_at"]),
            status=HITLStatus(d["status"]),
        )

    # ── HITLStore protocol ────────────────────────────────────────────────────

    async def save(self, request: HITLRequest) -> None:
        grace = self._grace_hours * 3600
        ttl = max(int((request.expires_at - datetime.now(UTC)).total_seconds() + grace), 1)
        pipe = self._r.pipeline()
        pipe.set(self._req_key(request.request_id), self._serialize(request), ex=ttl)
        pipe.zadd(self._pending_key, {request.request_id: request.expires_at.timestamp()})
        await pipe.execute()

    async def get(self, request_id: str) -> HITLRequest | None:
        data = await self._r.get(self._req_key(request_id))
        if data is not None:
            return self._deserialize(data)
        data = await self._r.get(self._expired_key(request_id))
        if data is not None:
            return self._deserialize(data)
        return None

    async def get_active(self, request_id: str) -> HITLRequest | None:
        data = await self._r.get(self._req_key(request_id))
        if data is None:
            return None
        return self._deserialize(data)

    async def pending_count(self) -> int:
        return await self._r.zcard(self._pending_key)

    async def get_pending_expired(self, now: datetime) -> list[HITLRequest]:
        ids: list[str] = await self._r.zrangebyscore(
            self._pending_key, "-inf", now.timestamp()
        )
        requests: list[HITLRequest] = []
        for rid in ids:
            data = await self._r.get(self._req_key(rid))
            if data is None:
                continue
            req = self._deserialize(data)
            if req.status == HITLStatus.PENDING:
                requests.append(req)
        return requests

    async def evict(self, request_id: str) -> None:
        pipe = self._r.pipeline()
        pipe.zrem(self._pending_key, request_id)
        pipe.delete(self._req_key(request_id))
        await pipe.execute()

    async def archive(self, request_id: str, request: HITLRequest) -> None:
        ttl = self._expired_days * 86400
        pipe = self._r.pipeline()
        pipe.zrem(self._pending_key, request_id)
        pipe.delete(self._req_key(request_id))
        pipe.set(self._expired_key(request_id), self._serialize(request), ex=ttl)
        await pipe.execute()
