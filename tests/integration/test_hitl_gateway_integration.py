"""Integration tests for HITLGateway state lifecycle.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011

These tests exercise the full HITL request lifecycle using InMemoryAuditStorage,
validating the state transitions and invariants defined in the spec without
requiring a real database or message broker.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from src.agents.hitl_gateway import (
    HITLDecision,
    HITLGateway,
    HITLGatewayError,
    HITLRequest,
    HITLStatus,
)
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_gateway(timeout_seconds: int = 3600) -> tuple[HITLGateway, InMemoryAuditStorage]:
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)
    gateway = HITLGateway(audit_logger=audit, broker=None, timeout_seconds=timeout_seconds)
    return gateway, storage


def _make_request(request_id: str = "req-001", risk_score: float = 0.8) -> HITLRequest:
    return HITLRequest(
        request_id=request_id,
        agent_id="test-agent",
        action_type="send_notification",
        action_parameters={"template": "account_update"},
        risk_score=risk_score,
        context_summary="User requested account update — context masked",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
    )


# ── Submit ────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_submit_creates_pending_request():
    gateway, _storage = _make_gateway()
    req = await gateway.submit_for_approval(_make_request())

    assert req.status == HITLStatus.PENDING
    assert req.expires_at > req.created_at


@pytest.mark.integration
@pytest.mark.asyncio
async def test_submit_writes_audit_record():
    gateway, storage = _make_gateway()
    await gateway.submit_for_approval(_make_request())

    events = await storage.query(agent_id="test-agent")
    assert len(events) == 1
    assert events[0].event_type == "hitl.request.submitted"
    assert events[0].outcome == "PENDING"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_submit_sets_timeout_from_config():
    gateway, _ = _make_gateway(timeout_seconds=120)
    req = await gateway.submit_for_approval(_make_request())

    delta = (req.expires_at - req.created_at).total_seconds()
    assert 118 <= delta <= 122  # allow 2s clock drift


# ── Approve ───────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_approve_transitions_to_approved():
    gateway, _ = _make_gateway()
    await gateway.submit_for_approval(_make_request("req-002"))

    decision = HITLDecision(
        request_id="req-002",
        decision=HITLStatus.APPROVED,
        approver_id="reviewer-01",
        rationale="Verified account change matches user intent.",
        decided_at=datetime.now(UTC),
    )
    result = await gateway.record_decision(decision)
    assert result.status == HITLStatus.APPROVED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_approve_writes_audit_decision_record():
    gateway, storage = _make_gateway()
    await gateway.submit_for_approval(_make_request("req-003"))

    await gateway.record_decision(
        HITLDecision(
            request_id="req-003",
            decision=HITLStatus.APPROVED,
            approver_id="reviewer-01",
            rationale="Approved.",
            decided_at=datetime.now(UTC),
        )
    )

    events = await storage.query(agent_id="test-agent")
    types = [e.event_type for e in events]
    assert "hitl.decision.recorded" in types


# ── Reject ────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reject_transitions_to_rejected():
    gateway, _ = _make_gateway()
    await gateway.submit_for_approval(_make_request("req-004"))

    result = await gateway.record_decision(
        HITLDecision(
            request_id="req-004",
            decision=HITLStatus.REJECTED,
            approver_id="reviewer-01",
            rationale="Action scope exceeds user permission.",
            decided_at=datetime.now(UTC),
        )
    )
    assert result.status == HITLStatus.REJECTED


# ── Expiry — timeout always rejects (spec invariant) ──────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expire_stale_marks_as_expired():
    # Use 0-second timeout so request is immediately stale
    gateway, _ = _make_gateway(timeout_seconds=0)
    await gateway.submit_for_approval(_make_request("req-005"))

    await asyncio.sleep(0.01)
    expired_ids = await gateway.expire_stale_requests()

    assert "req-005" in expired_ids
    retrieved = await gateway.get_request("req-005")
    assert retrieved is not None
    assert retrieved.status == HITLStatus.EXPIRED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_timeout_never_auto_approves():
    """Core safety invariant: timeout → EXPIRED, never APPROVED."""
    gateway, storage = _make_gateway(timeout_seconds=0)
    await gateway.submit_for_approval(_make_request("req-006"))

    await asyncio.sleep(0.01)
    await gateway.expire_stale_requests()

    events = await storage.query(agent_id="test-agent")
    outcomes = [e.outcome for e in events]
    assert "APPROVED" not in outcomes
    assert "EXPIRED_AUTO_REJECTED" in outcomes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_decision_on_expired_request_raises():
    gateway, _ = _make_gateway(timeout_seconds=0)
    await gateway.submit_for_approval(_make_request("req-007"))
    await asyncio.sleep(0.01)

    with pytest.raises(HITLGatewayError, match="expired"):
        await gateway.record_decision(
            HITLDecision(
                request_id="req-007",
                decision=HITLStatus.APPROVED,
                approver_id="reviewer-01",
                rationale="Too late.",
                decided_at=datetime.now(UTC),
            )
        )


# ── Guard: invalid state transitions ─────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_double_decision_raises():
    gateway, _ = _make_gateway()
    await gateway.submit_for_approval(_make_request("req-008"))

    decision = HITLDecision(
        request_id="req-008",
        decision=HITLStatus.APPROVED,
        approver_id="reviewer-01",
        rationale="First approval.",
        decided_at=datetime.now(UTC),
    )
    await gateway.record_decision(decision)

    with pytest.raises(HITLGatewayError):
        await gateway.record_decision(decision)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_decision_on_unknown_request_raises():
    gateway, _ = _make_gateway()

    with pytest.raises(HITLGatewayError, match="not found"):
        await gateway.record_decision(
            HITLDecision(
                request_id="nonexistent",
                decision=HITLStatus.APPROVED,
                approver_id="reviewer-01",
                rationale="Ghost approval.",
                decided_at=datetime.now(UTC),
            )
        )
