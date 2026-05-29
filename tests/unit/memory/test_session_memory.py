"""Unit tests for src/memory/session_memory.py.

Spec: specs/ai/agent-memory.md §3.3
ADR:  ADR-0017 (Agent Memory Architecture)

Uses fakeredis.aioredis for fully async, in-process Redis simulation.
No real Redis required.
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from src.memory.session_memory import SessionMemory

# ── fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture()
async def redis():
    server = fakeredis.aioredis.FakeRedis()
    yield server
    await server.aclose()


@pytest.fixture()
def memory(redis) -> SessionMemory:
    return SessionMemory(redis)


# ── set / get ─────────────────────────────────────────────────────────────────


class TestSessionMemorySetGet:
    @pytest.mark.asyncio
    async def test_set_and_get_string(self, memory: SessionMemory) -> None:
        await memory.set("session-1", "sprint_id", "sprint-42")
        result = await memory.get("session-1", "sprint_id")
        assert result == "sprint-42"

    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, memory: SessionMemory) -> None:
        value = {"decisions": ["d1", "d2"], "iteration": 3}
        await memory.set("session-2", "context", value)
        result = await memory.get("session-2", "context")
        assert result == value

    @pytest.mark.asyncio
    async def test_get_nonexistent_key_returns_none(self, memory: SessionMemory) -> None:
        result = await memory.get("session-x", "missing_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_overwrites_existing_key(self, memory: SessionMemory) -> None:
        await memory.set("session-1", "key", "original")
        await memory.set("session-1", "key", "updated")
        assert await memory.get("session-1", "key") == "updated"

    @pytest.mark.asyncio
    async def test_different_sessions_isolated(self, memory: SessionMemory) -> None:
        await memory.set("session-A", "key", "value-A")
        await memory.set("session-B", "key", "value-B")
        assert await memory.get("session-A", "key") == "value-A"
        assert await memory.get("session-B", "key") == "value-B"

    @pytest.mark.asyncio
    async def test_set_with_explicit_ttl(self, memory: SessionMemory) -> None:
        await memory.set("session-1", "key", "val", ttl_seconds=3600)
        result = await memory.get("session-1", "key")
        assert result == "val"

    @pytest.mark.asyncio
    async def test_integer_value_round_trips(self, memory: SessionMemory) -> None:
        await memory.set("session-1", "count", 42)
        assert await memory.get("session-1", "count") == 42

    @pytest.mark.asyncio
    async def test_list_value_round_trips(self, memory: SessionMemory) -> None:
        await memory.set("session-1", "items", [1, 2, 3])
        assert await memory.get("session-1", "items") == [1, 2, 3]


# ── get_all ───────────────────────────────────────────────────────────────────


class TestSessionMemoryGetAll:
    @pytest.mark.asyncio
    async def test_returns_all_keys_for_session(self, memory: SessionMemory) -> None:
        await memory.set("sess", "k1", "v1")
        await memory.set("sess", "k2", "v2")
        result = await memory.get_all("sess")
        assert result["k1"] == "v1"
        assert result["k2"] == "v2"

    @pytest.mark.asyncio
    async def test_empty_session_returns_empty_dict(self, memory: SessionMemory) -> None:
        result = await memory.get_all("no-such-session")
        assert result == {}

    @pytest.mark.asyncio
    async def test_other_session_keys_not_included(self, memory: SessionMemory) -> None:
        await memory.set("sess-A", "key", "A")
        await memory.set("sess-B", "key", "B")
        result = await memory.get_all("sess-A")
        assert "key" in result
        assert result["key"] == "A"


# ── delete_session ────────────────────────────────────────────────────────────


class TestSessionMemoryDeleteSession:
    @pytest.mark.asyncio
    async def test_deleted_session_keys_return_none(self, memory: SessionMemory) -> None:
        await memory.set("session-del", "k1", "v1")
        await memory.set("session-del", "k2", "v2")
        await memory.delete_session("session-del")
        assert await memory.get("session-del", "k1") is None
        assert await memory.get("session-del", "k2") is None

    @pytest.mark.asyncio
    async def test_delete_session_does_not_affect_other_sessions(
        self, memory: SessionMemory
    ) -> None:
        await memory.set("session-keep", "key", "safe")
        await memory.set("session-del", "key", "gone")
        await memory.delete_session("session-del")
        assert await memory.get("session-keep", "key") == "safe"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session_does_not_raise(self, memory: SessionMemory) -> None:
        await memory.delete_session("ghost-session")  # must not raise

    @pytest.mark.asyncio
    async def test_get_all_empty_after_delete(self, memory: SessionMemory) -> None:
        await memory.set("session-del", "key", "val")
        await memory.delete_session("session-del")
        result = await memory.get_all("session-del")
        assert result == {}
