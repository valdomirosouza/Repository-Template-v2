"""SessionMemory — short-term Redis-backed per-session key-value cache.

Spec: specs/ai/agent-memory.md §3.3
ADR:  ADR-0017 (Agent Memory Architecture)
DPIA: docs/privacy/dpia/dpia-agent-memory.md

PRIVACY INVARIANT: values stored via set() MUST be pii_filter-masked by the
caller before passing them here. SessionMemory does not apply masking.

Default TTL: settings.memory_session_ttl_seconds (86400 s = 24 h).
"""

from __future__ import annotations

import json
from typing import Any

from src.observability.logger import get_logger
from src.shared.config import settings

logger = get_logger("memory.session_memory")

_KEY_PREFIX = "agent:session"


def _redis_key(session_id: str, key: str) -> str:
    return f"{_KEY_PREFIX}:{session_id}:{key}"


def _index_key(session_id: str) -> str:
    return f"{_KEY_PREFIX}:{session_id}:__keys__"


class SessionMemory:
    """Short-term memory scoped to an agent session.

    Uses Redis SETEX for TTL-based expiry. Each value is JSON-serialised so
    arbitrary Python objects can be stored (as long as they are JSON-serialisable).

    Usage::

        memory = SessionMemory(redis_client)
        await memory.set("session-1", "last_sprint_id", "sprint-42")
        value = await memory.get("session-1", "last_sprint_id")
        await memory.delete_session("session-1")

    Spec: specs/ai/agent-memory.md §3.3
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def set(
        self,
        session_id: str,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store a value. TTL defaults to settings.memory_session_ttl_seconds.

        PRIVACY: caller must mask value with pii_filter before calling.
        """
        ttl = ttl_seconds if ttl_seconds is not None else settings.memory_session_ttl_seconds
        rkey = _redis_key(session_id, key)
        serialised = json.dumps(value)

        await self._redis.setex(rkey, ttl, serialised)

        # Track key membership so get_all() can enumerate them
        idx_key = _index_key(session_id)
        await self._redis.sadd(idx_key, key)
        await self._redis.expire(idx_key, ttl)

        logger.info("Session memory set", session_id=session_id, key=key, ttl=ttl)

    async def get(self, session_id: str, key: str) -> Any | None:
        """Retrieve a stored value. Returns None if the key is absent or expired."""
        rkey = _redis_key(session_id, key)
        raw = await self._redis.get(rkey)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Session memory value could not be decoded", session_id=session_id, key=key
            )
            return None

    async def get_all(self, session_id: str) -> dict[str, Any]:
        """Return all non-expired keys for a session."""
        idx_key = _index_key(session_id)
        raw_keys = await self._redis.smembers(idx_key)
        if not raw_keys:
            return {}

        result: dict[str, Any] = {}
        for k in raw_keys:
            key_str = k.decode() if isinstance(k, bytes) else str(k)
            val = await self.get(session_id, key_str)
            if val is not None:
                result[key_str] = val
        return result

    async def delete_session(self, session_id: str) -> None:
        """Delete all keys for a session (e.g. on erasure request or session end)."""
        idx_key = _index_key(session_id)
        raw_keys = await self._redis.smembers(idx_key)

        keys_to_delete = [
            _redis_key(session_id, k.decode() if isinstance(k, bytes) else str(k)) for k in raw_keys
        ]
        keys_to_delete.append(idx_key)

        if keys_to_delete:
            await self._redis.delete(*keys_to_delete)

        logger.info(
            "Session memory deleted", session_id=session_id, keys_deleted=len(keys_to_delete)
        )
