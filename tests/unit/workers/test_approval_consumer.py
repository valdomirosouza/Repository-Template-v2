"""Unit tests for src/workers/approval_consumer.py (W12-T2, issue #355, ADR-0086).

The consumer resolves the *stored* HITL request, executes it through ToolExecutor with
hitl_approved=True, and settles the suspended domain request honestly. Everything is in-memory:
InMemoryBroker (with subscriptions), InMemoryHITLStore, InMemoryRequestStore, a mocked executor.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.hitl_gateway import HITLGateway, HITLRequest, HITLStatus
from src.agents.hitl_store import InMemoryHITLStore
from src.agents.request_store import InMemoryRequestStore, RequestState
from src.agents.tool_executor import ToolExecutionResult
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
from src.shared.broker import InMemoryBroker
from src.workers.approval_consumer import (
    TOPIC_APPROVED,
    TOPIC_EXPIRED,
    TOPIC_REJECTED,
    TOPICS,
    ApprovalConsumer,
)

pytestmark = pytest.mark.unit

_AGENT = "agent-00000000-0000-0000-0000-000000000001"


def _executed(outcome: str = "EXECUTED", error: str | None = None) -> ToolExecutionResult:
    return ToolExecutionResult(
        action_type="write-file", outcome=outcome, result={"ok": outcome == "EXECUTED"}, error=error
    )


async def _seed(hitl_id: str = "hitl-001", domain_id: str = "req-001") -> dict[str, Any]:
    audit = AuditLogger(InMemoryAuditStorage())
    store = InMemoryHITLStore()
    broker = InMemoryBroker()
    gateway = HITLGateway(audit_logger=audit, broker=broker, store=store)
    now = datetime.now(UTC)
    req = HITLRequest(
        request_id=hitl_id,
        agent_id=_AGENT,
        action_type="write_file",
        action_parameters={"path": "/tmp/report.txt"},
        risk_score=0.85,
        context_summary="synthetic",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    await store.save(req)
    requests = InMemoryRequestStore()
    await requests.save(
        RequestState(
            request_id=domain_id,
            status="waiting_for_human_approval",
            created_at=now,
            updated_at=now,
            result={"status": "waiting_for_human_approval", "hitl_request_id": hitl_id},
        )
    )
    executor = MagicMock()
    executor.execute = AsyncMock(return_value=_executed())
    consumer = ApprovalConsumer(
        hitl_gateway=gateway,
        request_store=requests,
        tool_executor=executor,
        audit_logger=audit,
        broker=broker,
    )
    return {
        "consumer": consumer,
        "executor": executor,
        "requests": requests,
        "audit": audit,
        "broker": broker,
        "gateway": gateway,
        "hitl": req,
    }


async def test_approved_executes_stored_action_with_hitl_approved_flag():
    ctx = await _seed()
    await ctx["consumer"].handle_event(
        TOPIC_APPROVED, {"request_id": "hitl-001", "decision": "APPROVED", "rationale": "ok"}
    )
    ctx["executor"].execute.assert_awaited_once()
    kwargs = ctx["executor"].execute.await_args.kwargs
    args = ctx["executor"].execute.await_args.args
    assert args[0] == "write_file" and args[1] == {"path": "/tmp/report.txt"}
    assert kwargs["hitl_approved"] is True and kwargs["agent_id"] == _AGENT
    state = await ctx["requests"].get("req-001")
    assert state is not None and state.status == "completed"
    assert state.result["outcome"] == "EXECUTED" and state.result["hitl_request_id"] == "hitl-001"


async def test_approved_but_executor_reports_blocked_marks_failed():
    ctx = await _seed()
    ctx["executor"].execute = AsyncMock(return_value=_executed("BLOCKED", "sandbox required"))
    await ctx["consumer"].handle_event(
        TOPIC_APPROVED, {"request_id": "hitl-001", "decision": "APPROVED"}
    )
    state = await ctx["requests"].get("req-001")
    assert state is not None and state.status == "failed"
    assert state.error == "sandbox required"


async def test_executor_exception_is_audited_and_marks_failed_not_raised():
    ctx = await _seed()
    ctx["executor"].execute = AsyncMock(side_effect=RuntimeError("tool exploded"))
    await ctx["consumer"].handle_event(
        TOPIC_APPROVED, {"request_id": "hitl-001", "decision": "APPROVED"}
    )
    state = await ctx["requests"].get("req-001")
    assert state is not None and state.status == "failed" and "tool exploded" in (state.error or "")
    storage = ctx["audit"]._storage  # type: ignore[attr-defined]
    events = [e for e in storage._records if e.event_type == "agent.action.failed"]
    assert events and events[0].outcome == "FAILED_AFTER_APPROVAL"


async def test_rejected_and_expired_settle_without_executing():
    ctx = await _seed()
    await ctx["consumer"].handle_event(
        TOPIC_REJECTED, {"request_id": "hitl-001", "decision": "REJECTED"}
    )
    assert (await ctx["requests"].get("req-001")).status == "rejected"
    ctx["executor"].execute.assert_not_awaited()

    ctx2 = await _seed(hitl_id="hitl-002", domain_id="req-002")
    await ctx2["consumer"].handle_event(TOPIC_EXPIRED, {"request_id": "hitl-002"})
    assert (await ctx2["requests"].get("req-002")).status == "expired"
    ctx2["executor"].execute.assert_not_awaited()


async def test_duplicate_delivery_is_idempotent():
    ctx = await _seed()
    payload = {"request_id": "hitl-001", "decision": "APPROVED"}
    await ctx["consumer"].handle_event(TOPIC_APPROVED, payload)
    await ctx["consumer"].handle_event(TOPIC_APPROVED, payload)
    ctx["executor"].execute.assert_awaited_once()


async def test_unknown_hitl_request_is_skipped():
    ctx = await _seed()
    await ctx["consumer"].handle_event(
        TOPIC_APPROVED, {"request_id": "hitl-nope", "decision": "APPROVED"}
    )
    ctx["executor"].execute.assert_not_awaited()
    await ctx["consumer"].handle_event(TOPIC_APPROVED, {})  # no request_id at all
    ctx["executor"].execute.assert_not_awaited()


async def test_in_memory_transport_closes_the_loop_through_the_gateway():
    """record_decision → broker.publish → subscribed consumer → executed → status completed."""
    ctx = await _seed()
    task = asyncio.create_task(ctx["consumer"].run())
    await asyncio.sleep(0)  # let run() subscribe
    assert all(t in ctx["broker"]._subscribers for t in TOPICS)

    from src.agents.hitl_gateway import HITLDecision

    await ctx["gateway"].record_decision(
        HITLDecision(
            request_id="hitl-001",
            decision=HITLStatus.APPROVED,
            approver_id="operator-00000000-0000-0000-0000-000000000001",
            rationale="Verified against approved scope.",
            decided_at=datetime.now(UTC),
        )
    )
    state = await ctx["requests"].get("req-001")
    assert state is not None and state.status == "completed"
    await ctx["consumer"].stop()
    await task
    assert not any(ctx["broker"]._subscribers[t] for t in TOPICS)
