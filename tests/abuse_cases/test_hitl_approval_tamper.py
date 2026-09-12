"""Abuse case: approve-then-tamper (W12-T2, ADR-0086, ADR-0050).

Attack vector: an attacker who can write to the approval topic (or replay a captured event)
publishes ``agent.action.approved`` with a *different* action or parameters than the one the
human reviewed, hoping the executor runs the tampered payload under the approval.

Mitigation tested: the ApprovalConsumer executes only what the HITL store holds for that
request id — the event payload is a trigger, never the source of the action. A tampered
action_type/parameters in the event must have no effect, and a forged approval for a request
the store never saw must execute nothing.

All tests use mocks — no real API calls. Synthetic identifiers only.

Spec: specs/ai/hitl-hotl.md · secure-by-design-agentic-ai-compliance-v2.md §Pillar 4 (CV2)
ADR:  ADR-0050, ADR-0086
Issue: #355
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.hitl_gateway import HITLGateway, HITLRequest
from src.agents.hitl_store import InMemoryHITLStore
from src.agents.request_store import InMemoryRequestStore, RequestState
from src.agents.tool_executor import ToolExecutionResult
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
from src.shared.broker import InMemoryBroker
from src.workers.approval_consumer import TOPIC_APPROVED, ApprovalConsumer

pytestmark = pytest.mark.abuse_case

_REVIEWED_ACTION = "write_file"
_REVIEWED_PARAMS = {"path": "/tmp/report.txt"}
_TAMPERED_ACTION = "execute-code"
_TAMPERED_PARAMS = {"code": "SYNTHETIC_MALICIOUS_PAYLOAD"}


async def _consumer_with_reviewed_request(hitl_id: str = "hitl-abuse-001"):
    audit = AuditLogger(InMemoryAuditStorage())
    store = InMemoryHITLStore()
    now = datetime.now(UTC)
    await store.save(
        HITLRequest(
            request_id=hitl_id,
            agent_id="agent-00000000-0000-0000-0000-000000000001",
            action_type=_REVIEWED_ACTION,
            action_parameters=dict(_REVIEWED_PARAMS),
            risk_score=0.8,
            context_summary="synthetic",
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
    )
    requests = InMemoryRequestStore()
    await requests.save(
        RequestState(
            request_id="req-abuse-001",
            status="waiting_for_human_approval",
            created_at=now,
            updated_at=now,
            result={"hitl_request_id": hitl_id},
        )
    )
    executor = MagicMock()
    executor.execute = AsyncMock(
        return_value=ToolExecutionResult(action_type=_REVIEWED_ACTION, outcome="EXECUTED")
    )
    consumer = ApprovalConsumer(
        hitl_gateway=HITLGateway(audit_logger=audit, broker=None, store=store),
        request_store=requests,
        tool_executor=executor,
        audit_logger=audit,
        broker=InMemoryBroker(),
    )
    return consumer, executor


@pytest.mark.abuse_case
class TestApproveThenTamper:
    async def test_tampered_event_payload_cannot_change_the_executed_action(self) -> None:
        consumer, executor = await _consumer_with_reviewed_request()
        await consumer.handle_event(
            TOPIC_APPROVED,
            {
                "request_id": "hitl-abuse-001",
                "decision": "APPROVED",
                "action_type": _TAMPERED_ACTION,
                "action_parameters": _TAMPERED_PARAMS,
                "parameters": _TAMPERED_PARAMS,
            },
        )
        executor.execute.assert_awaited_once()
        args = executor.execute.await_args.args
        assert args[0] == _REVIEWED_ACTION and args[1] == _REVIEWED_PARAMS
        assert _TAMPERED_ACTION not in str(executor.execute.await_args)

    async def test_forged_approval_for_unreviewed_request_executes_nothing(self) -> None:
        consumer, executor = await _consumer_with_reviewed_request()
        await consumer.handle_event(
            TOPIC_APPROVED,
            {
                "request_id": "hitl-never-reviewed",
                "decision": "APPROVED",
                "action_type": _TAMPERED_ACTION,
            },
        )
        executor.execute.assert_not_awaited()

    async def test_replayed_approval_does_not_execute_twice(self) -> None:
        consumer, executor = await _consumer_with_reviewed_request()
        payload = {"request_id": "hitl-abuse-001", "decision": "APPROVED"}
        await consumer.handle_event(TOPIC_APPROVED, payload)
        await consumer.handle_event(TOPIC_APPROVED, payload)
        executor.execute.assert_awaited_once()

    async def test_decision_field_cannot_upgrade_a_rejection_on_the_approved_topic(self) -> None:
        """A REJECTED decision carried on the approved topic is settled as rejected, not run."""
        consumer, executor = await _consumer_with_reviewed_request()
        await consumer.handle_event(
            TOPIC_APPROVED, {"request_id": "hitl-abuse-001", "decision": "REJECTED"}
        )
        executor.execute.assert_not_awaited()
