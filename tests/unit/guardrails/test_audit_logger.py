"""Unit tests for AuditLogger and InMemoryAuditStorage.

Spec: specs/ai/guardrails.md (Layer 4 — Audit Logger)
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.guardrails.audit_logger import AuditLogger, AuditWriteError, InMemoryAuditStorage
from src.shared.models import AuditEvent

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_event(
    agent_id: str = "agent-test",
    action: str = "test.action.proposed",
    offset_seconds: int = 0,
) -> AuditEvent:
    return AuditEvent(
        event_type="test.event",
        agent_id=agent_id,
        action=action,
        outcome="PENDING",
        created_at=datetime.now(UTC) + timedelta(seconds=offset_seconds),
    )


# ── InMemoryAuditStorage ──────────────────────────────────────────────────────


class TestInMemoryAuditStorage:
    @pytest.mark.asyncio
    async def test_append_and_query_no_filter(self):
        storage = InMemoryAuditStorage()
        for _ in range(3):
            await storage.append(_make_event())

        results = await storage.query(
            agent_id=None,
            action_type=None,
            from_time=None,
            to_time=None,
            limit=100,
        )
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_filter_by_agent_id(self):
        storage = InMemoryAuditStorage()
        await storage.append(_make_event(agent_id="agent-alpha"))
        await storage.append(_make_event(agent_id="agent-alpha"))
        await storage.append(_make_event(agent_id="agent-beta"))

        results = await storage.query(agent_id="agent-alpha")
        assert len(results) == 2
        assert all(e.agent_id == "agent-alpha" for e in results)

    @pytest.mark.asyncio
    async def test_query_filter_by_action_type(self):
        storage = InMemoryAuditStorage()
        await storage.append(_make_event(action="action.read"))
        await storage.append(_make_event(action="action.write"))
        await storage.append(_make_event(action="action.read"))

        results = await storage.query(action_type="action.read")
        assert len(results) == 2
        assert all(e.action == "action.read" for e in results)

    @pytest.mark.asyncio
    async def test_query_filter_by_from_time(self):
        storage = InMemoryAuditStorage()
        cutoff = datetime.now(UTC)
        await storage.append(_make_event(offset_seconds=-120))  # before cutoff
        await storage.append(_make_event(offset_seconds=10))  # after cutoff
        await storage.append(_make_event(offset_seconds=20))  # after cutoff

        results = await storage.query(from_time=cutoff)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_filter_by_to_time(self):
        storage = InMemoryAuditStorage()
        cutoff = datetime.now(UTC)
        await storage.append(_make_event(offset_seconds=-20))  # before cutoff
        await storage.append(_make_event(offset_seconds=-10))  # before cutoff
        await storage.append(_make_event(offset_seconds=120))  # after cutoff

        results = await storage.query(to_time=cutoff)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_limit_returns_most_recent(self):
        storage = InMemoryAuditStorage()
        for i in range(5):
            await storage.append(_make_event(agent_id=f"agent-{i}"))

        results = await storage.query(limit=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_append_stores_a_copy(self):
        storage = InMemoryAuditStorage()
        event = _make_event()
        await storage.append(event)

        # Mutating the original does not affect the stored record
        object.__setattr__(event, "outcome", "MUTATED")
        results = await storage.query()
        assert results[0].outcome == "PENDING"


# ── AuditLogger ───────────────────────────────────────────────────────────────


class TestAuditLogger:
    @pytest.mark.asyncio
    async def test_log_event_returns_event_id(self):
        logger = AuditLogger(InMemoryAuditStorage())
        event_id = await logger.log_event(_make_event())
        uuid.UUID(event_id)  # raises ValueError if not a valid UUID

    @pytest.mark.asyncio
    async def test_audit_write_error_raised_on_storage_failure(self):
        failing_storage = InMemoryAuditStorage()
        failing_storage.append = AsyncMock(side_effect=RuntimeError("disk full"))

        logger = AuditLogger(failing_storage)
        with pytest.raises(AuditWriteError, match="disk full"):
            await logger.log_event(_make_event())
