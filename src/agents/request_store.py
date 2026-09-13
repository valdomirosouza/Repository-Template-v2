"""Request state store — in-memory (tests/local dev) and Redis (production).

Mirrors the HITLStore protocol pattern from src/agents/hitl_store.py.

Spec: specs/system/request-pipeline.md
ADR:  ADR-0009 (Caching Strategy)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from src.shared.config import settings


@dataclass
class RequestState:
    request_id: str
    status: str  # queued|processing|waiting_for_human_approval|completed|rejected|expired|failed
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: str | None = None


class RequestStoreProtocol(Protocol):
    """Persistence contract for request state.

    Implementations: InMemoryRequestStore (local/test) and RedisRequestStore (production).
    """

    async def save(self, state: RequestState) -> None: ...

    async def get(self, request_id: str) -> RequestState | None: ...

    async def get_by_hitl_request_id(self, hitl_request_id: str) -> RequestState | None:
        """Resolve the domain request suspended on a HITL request (W12-T2, issue #355)."""
        ...


class InMemoryRequestStore:
    """Local/test store. Keeps a secondary index hitl_request_id -> request_id (W12-T2)."""

    def __init__(self) -> None:
        self._data: dict[str, RequestState] = {}
        self._hitl_link: dict[str, str] = {}

    async def save(self, state: RequestState) -> None:
        self._data[state.request_id] = state
        hitl_id = _hitl_id_of(state)
        if hitl_id:
            self._hitl_link[hitl_id] = state.request_id

    async def get(self, request_id: str) -> RequestState | None:
        return self._data.get(request_id)

    async def get_by_hitl_request_id(self, hitl_request_id: str) -> RequestState | None:
        request_id = self._hitl_link.get(hitl_request_id)
        return self._data.get(request_id) if request_id else None


def _hitl_id_of(state: RequestState) -> str | None:
    result = state.result or {}
    hitl_id = result.get("hitl_request_id")
    return str(hitl_id) if hitl_id else None


class RedisRequestStore:
    """Redis-backed store; mirrors HITLRedisStore key/TTL pattern."""

    def __init__(self, client: Any) -> None:
        self._r = client

    def _key(self, request_id: str) -> str:
        return f"{settings.request_redis_key_prefix}:state:{request_id}"

    async def save(self, state: RequestState) -> None:
        data = {
            "request_id": state.request_id,
            "status": state.status,
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "result": state.result,
            "error": state.error,
        }
        ttl = settings.request_result_ttl_hours * 3600
        await self._r.set(self._key(state.request_id), json.dumps(data), ex=ttl)
        hitl_id = _hitl_id_of(state)
        if hitl_id:  # secondary index for the ApprovalConsumer (W12-T2)
            await self._r.set(self._hitl_key(hitl_id), state.request_id, ex=ttl)

    def _hitl_key(self, hitl_request_id: str) -> str:
        return f"{settings.request_redis_key_prefix}:hitl_link:{hitl_request_id}"

    async def get_by_hitl_request_id(self, hitl_request_id: str) -> RequestState | None:
        request_id = await self._r.get(self._hitl_key(hitl_request_id))
        if request_id is None:
            return None
        if isinstance(request_id, bytes):
            request_id = request_id.decode()
        return await self.get(str(request_id))

    async def get(self, request_id: str) -> RequestState | None:
        raw = await self._r.get(self._key(request_id))
        if raw is None:
            return None
        d = json.loads(raw)
        return RequestState(
            request_id=d["request_id"],
            status=d["status"],
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            result=d.get("result"),
            error=d.get("error"),
        )
