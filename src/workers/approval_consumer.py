"""HITL approval consumer — closes the human-approval loop (W12-T2, issue #355).

Before this worker existed the loop was open: ``HITLGateway.record_decision`` published
``agent.action.approved`` / ``agent.action.rejected`` and nothing consumed either topic, while
the request consumer had already written the domain request as ``completed`` the moment the
orchestrator returned ``waiting_for_human_approval``. A human approved and nothing executed.

Responsibilities:

  1. Consume ``agent.action.approved`` / ``.rejected`` / ``.expired``.
  2. Resolve the archived :class:`HITLRequest` (action type + parameters) via the gateway.
  3. On approval, execute the action through :class:`ToolExecutor` with ``hitl_approved=True``
     — registry and sandbox enforcement are never skipped, only the HITL/autonomy checks a human
     has just satisfied (ADR-0016, ADR-0039).
  4. Move the suspended domain request (found by ``hitl_request_id``) to an honest terminal
     status: ``completed`` / ``failed`` / ``rejected`` / ``expired``.
  5. Audit every outcome (``agent.action.executed`` / ``agent.action.failed`` / decision echo).

Transport: aiokafka when Kafka is available; ``InMemoryBroker.subscribe`` otherwise, so the
in-process app behaves the same way end-to-end (the lifespan wiring test relies on this).

Spec: specs/ai/hitl-hotl.md · ADR-0011, ADR-0046, ADR-0086
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.agents.hitl_gateway import HITLGateway, HITLStatus
from src.agents.request_store import RequestState, RequestStoreProtocol
from src.agents.tool_executor import ToolExecutor
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.observability.metrics import CONSUMER_HEARTBEAT_TIMESTAMP
from src.shared.broker import InMemoryBroker
from src.shared.config import settings
from src.shared.models import AuditEvent

if TYPE_CHECKING:
    from src.shared.broker import EventBrokerProtocol

logger = get_logger("approval_consumer")

TOPIC_APPROVED = "agent.action.approved"
TOPIC_REJECTED = "agent.action.rejected"
TOPIC_EXPIRED = "agent.action.expired"
TOPICS: tuple[str, ...] = (TOPIC_APPROVED, TOPIC_REJECTED, TOPIC_EXPIRED)

TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed", "rejected", "expired"})
AUTONOMY_LEVEL_HITL = "HITL_APPROVED"  # label only; the executor skips the autonomy check


class ApprovalConsumer:
    """Execute HITL-approved actions and settle the suspended domain request."""

    def __init__(
        self,
        *,
        hitl_gateway: HITLGateway,
        request_store: RequestStoreProtocol,
        tool_executor: ToolExecutor,
        audit_logger: AuditLogger,
        broker: EventBrokerProtocol,
    ) -> None:
        self._hitl = hitl_gateway
        self._store = request_store
        self._executor = tool_executor
        self._audit = audit_logger
        self._broker = broker
        self._running = False
        self._stopped = asyncio.Event()

    # ── transport ──────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Consume until stopped. In-memory broker → subscription; Kafka → aiokafka loop."""
        self._running = True
        if isinstance(self._broker, InMemoryBroker):
            for topic in TOPICS:
                self._broker.subscribe(topic, self.handle_event)
            logger.info("Approval consumer subscribed (in-memory)", topics=list(TOPICS))
            try:
                await self._stopped.wait()
            finally:
                for topic in TOPICS:
                    self._broker.unsubscribe(topic, self.handle_event)
            return

        from aiokafka import AIOKafkaConsumer, TopicPartition  # lazy: keeps tests fast

        consumer = AIOKafkaConsumer(
            *TOPICS,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=f"{settings.kafka_consumer_group}-approvals",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        await consumer.start()
        logger.info("Approval consumer started", topics=list(TOPICS))
        try:
            async for msg in consumer:
                if not self._running:
                    break
                try:
                    payload = json.loads(msg.value)
                except Exception as exc:
                    logger.error("Unparseable approval event", topic=msg.topic, error=str(exc))
                else:
                    await self.handle_event(msg.topic, payload)
                tp = TopicPartition(msg.topic, msg.partition)
                await consumer.commit({tp: msg.offset + 1})
                CONSUMER_HEARTBEAT_TIMESTAMP.labels(
                    f"{settings.kafka_consumer_group}-approvals"
                ).set(datetime.now(UTC).timestamp())
        finally:
            await consumer.stop()
            logger.info("Approval consumer stopped")

    async def stop(self) -> None:
        self._running = False
        self._stopped.set()

    # ── core ───────────────────────────────────────────────────────────────────

    async def handle_event(self, topic: str, payload: dict[str, Any]) -> None:
        """Settle one HITL outcome. Idempotent: a terminal domain request is left untouched."""
        hitl_id = str(payload.get("request_id") or "")
        if not hitl_id:
            logger.warning("Approval event without request_id — skipping", topic=topic)
            return

        hitl_request = await self._hitl.get_request(hitl_id)
        if hitl_request is None:
            logger.warning("HITL request not found for approval event", hitl_request_id=hitl_id)
            return

        domain = await self._store.get_by_hitl_request_id(hitl_id)
        if domain is not None and domain.status in TERMINAL_STATUSES:
            logger.info("Domain request already settled — skipping", request_id=domain.request_id)
            return

        decision = str(payload.get("decision") or hitl_request.status.value).upper()
        trace_id = hitl_request.otel_trace_id or None

        if topic == TOPIC_APPROVED and decision == HITLStatus.APPROVED.value:
            status, result = await self._execute_approved(hitl_request, trace_id)
        elif topic == TOPIC_EXPIRED or decision == HITLStatus.EXPIRED.value:
            status, result = "expired", {"outcome": "EXPIRED_AUTO_REJECTED"}
        else:
            status, result = "rejected", {"outcome": "REJECTED"}

        result.update(
            {
                "hitl_request_id": hitl_id,
                "action_type": hitl_request.action_type,
                "decision": decision,
                "rationale": payload.get("rationale"),
            }
        )
        if domain is not None:
            await self._store.save(
                RequestState(
                    request_id=domain.request_id,
                    status=status,
                    created_at=domain.created_at,
                    updated_at=datetime.now(UTC),
                    result={**(domain.result or {}), **result},
                    error=result.get("error"),
                )
            )
        logger.info(
            "HITL outcome settled",
            hitl_request_id=hitl_id,
            request_id=domain.request_id if domain else None,
            status=status,
        )

    async def _execute_approved(
        self, hitl_request: Any, trace_id: str | None
    ) -> tuple[str, dict[str, Any]]:
        try:
            exec_result = await self._executor.execute(
                hitl_request.action_type,
                hitl_request.action_parameters,
                autonomy_level=AUTONOMY_LEVEL_HITL,
                agent_id=hitl_request.agent_id,
                trace_id=trace_id,
                hitl_approved=True,
            )
        except Exception as exc:  # registry/sandbox/tool failure — surface, never swallow
            await self._audit.log_event(
                AuditEvent(
                    event_type="agent.action.failed",
                    agent_id=hitl_request.agent_id,
                    action=hitl_request.action_type,
                    outcome="FAILED_AFTER_APPROVAL",
                    risk_score=hitl_request.risk_score,
                    metadata={"hitl_request_id": hitl_request.request_id, "error": str(exc)},
                    trace_id=trace_id,
                )
            )
            return "failed", {"outcome": "FAILED", "error": str(exc)}

        outcome = exec_result.outcome
        status = "completed" if outcome == "EXECUTED" else "failed"
        await self._audit.log_event(
            AuditEvent(
                event_type="agent.action.executed"
                if status == "completed"
                else "agent.action.failed",
                agent_id=hitl_request.agent_id,
                action=hitl_request.action_type,
                outcome=outcome,
                risk_score=hitl_request.risk_score,
                metadata={
                    "hitl_request_id": hitl_request.request_id,
                    "sandbox_used": exec_result.sandbox_used,
                    "hitl_approved": True,
                },
                trace_id=trace_id,
            )
        )
        return status, {
            "outcome": outcome,
            "tool_result": exec_result.result,
            "sandbox_used": exec_result.sandbox_used,
            "error": exec_result.error,
        }
