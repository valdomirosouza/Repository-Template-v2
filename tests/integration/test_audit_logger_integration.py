"""Integration tests for AuditLogger write-before-execute invariant.

Spec: specs/ai/guardrails.md (Layer 4 — Audit Logger)
ADR:  ADR-0011 (write-before-execute invariant)

Validates that:
- Every action produces an immutable audit record
- A storage failure raises AuditWriteError and blocks the action
- Records are queryable by agent_id, action_type, and time range
"""

from __future__ import annotations

import pytest

from src.guardrails.audit_logger import AuditLogger, AuditWriteError, InMemoryAuditStorage
from src.shared.models import AuditEvent


def _make_event(
    event_type: str = "agent_action",
    agent_id: str = "test-agent",
    action: str = "read_document",
    outcome: str = "success",
) -> AuditEvent:
    return AuditEvent(
        event_type=event_type,
        agent_id=agent_id,
        action=action,
        outcome=outcome,
    )


# ── Write-before-execute invariant ────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_successful_write_returns_event_id():
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)

    event_id = await audit.log_event(_make_event())
    assert event_id is not None
    assert len(event_id) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_failed_write_raises_audit_write_error():
    """AuditWriteError must be raised — callers must block the action."""

    class FailingStorage:
        async def append(self, event: object) -> None:
            raise RuntimeError("Disk full")

        async def query(self, **_: object) -> list:
            return []

    audit = AuditLogger(storage_backend=FailingStorage())

    with pytest.raises(AuditWriteError):
        await audit.log_event(_make_event())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_events_all_persisted():
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)

    for i in range(10):
        await audit.log_event(_make_event(action=f"action_{i}"))

    events = await audit.query_events(agent_id="test-agent")
    assert len(events) == 10


# ── Append-only semantics ─────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_records_are_immutable_after_write():
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)

    event = _make_event(outcome="pending")
    await audit.log_event(event)

    events = await audit.query_events(agent_id="test-agent")
    assert events[0].outcome == "pending"

    # Mutating the original object must not affect the stored record
    object.__setattr__(event, "outcome", "tampered")
    events_after = await audit.query_events(agent_id="test-agent")
    assert events_after[0].outcome == "pending"


# ── Query filtering ───────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_by_agent_id():
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)

    await audit.log_event(_make_event(agent_id="agent-a", action="read"))
    await audit.log_event(_make_event(agent_id="agent-b", action="write"))
    await audit.log_event(_make_event(agent_id="agent-a", action="summarise"))

    results = await audit.query_events(agent_id="agent-a")
    assert len(results) == 2
    assert all(e.agent_id == "agent-a" for e in results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_by_action_type():
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)

    await audit.log_event(_make_event(action="read_document"))
    await audit.log_event(_make_event(action="send_notification"))
    await audit.log_event(_make_event(action="read_document"))

    results = await audit.query_events(action_type="read_document")
    assert len(results) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_limit_respected():
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)

    for i in range(20):
        await audit.log_event(_make_event(action=f"action_{i}"))

    results = await audit.query_events(agent_id="test-agent", limit=5)
    assert len(results) == 5


# ── HITL events audit trail ───────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hitl_full_lifecycle_audit_trail():
    """A complete HITL approval sequence produces a traceable 3-event audit trail."""
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)

    await audit.log_event(_make_event(event_type="hitl.request.submitted", outcome="PENDING"))
    await audit.log_event(_make_event(event_type="hitl.decision.recorded", outcome="APPROVED"))
    await audit.log_event(_make_event(event_type="agent.action.executed", outcome="success"))

    events = await audit.query_events(agent_id="test-agent")
    event_types = [e.event_type for e in events]

    assert "hitl.request.submitted" in event_types
    assert "hitl.decision.recorded" in event_types
    assert "agent.action.executed" in event_types
