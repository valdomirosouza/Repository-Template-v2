"""Domain request consumer — reads domain.request.created, drives AgentOrchestrator.

Runs as an asyncio background task in the FastAPI lifespan.

Production note: in a multi-service deployment this worker runs as a separate
process/Deployment, not co-located with the API server. The in-process approach
used here is intentional for self-contained template demonstration.

Wiring (W12, issues #354/#355/#356/#359): the lifespan injects the production LLM client
(built once by ``build_llm_client``), the agent concurrency semaphore, and — when
``harness_mode`` is not ``solo`` — the ``HarnessCoordinator``. One orchestrator is built per
message, not per retry attempt. A ``waiting_for_human_approval`` outcome is stored under that
status (not ``completed``); the ApprovalConsumer settles it once a human decides.

Spec: specs/system/request-pipeline.md
ADR:  ADR-0003 (Async API Strategy), ADR-0011 (HITL/HOTL Model), ADR-0086, ADR-0089
REM:  REM-012 (DLQ + safe offset commit), REM-013 (consumer heartbeat)
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.agents.hitl_gateway import HITLGateway
from src.agents.orchestrator.orchestrator import AgentOrchestrator
from src.agents.request_store import RequestState, RequestStoreProtocol
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.observability.metrics import (
    AGENT_SEMAPHORE_WAITING,
    CONSUMER_HEARTBEAT_TIMESTAMP,
    DLQ_MESSAGES_COUNTER,
)
from src.shared.broker import InMemoryBroker
from src.shared.config import settings

if TYPE_CHECKING:
    from src.agents.harness.coordinator import HarnessCoordinator
    from src.shared.broker import EventBrokerProtocol
    from src.shared.llm_client import LLMClient

logger = get_logger("request_consumer")

TOPIC = "domain.request.created"
STATUS_WAITING = "waiting_for_human_approval"


class RequestConsumer:
    """Kafka consumer that drives AgentOrchestrator processing for each submitted request.

    Start via asyncio.create_task(consumer.run()) in the FastAPI lifespan.
    Stop by cancelling the task or calling stop() before cancellation.

    Offset safety (REM-012): enable_auto_commit=False. The offset is committed only
    after _handle() returns — whether the message succeeded or was routed to the DLQ.
    This prevents both silent message loss and infinite reprocessing of poison messages.
    """

    def __init__(
        self,
        store: RequestStoreProtocol,
        audit_logger: AuditLogger,
        hitl_gateway: HITLGateway,
        broker: EventBrokerProtocol,
        *,
        llm_client: LLMClient | None = None,
        semaphore: asyncio.Semaphore | None = None,
        harness: HarnessCoordinator | None = None,
    ) -> None:
        self._store = store
        self._audit = audit_logger
        self._hitl = hitl_gateway
        self._broker = broker
        self._llm = llm_client
        self._semaphore = semaphore
        self._harness = harness
        self._running = False
        self._stopped = asyncio.Event()

    # ── transport ──────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main consume loop. Designed to be started as asyncio.create_task()."""
        self._running = True
        if isinstance(self._broker, InMemoryBroker):
            # Kafka unavailable: consume the in-process event stream so the pipeline still
            # runs end-to-end (W12-T1). Previously this loop tried aiokafka and died silently.
            self._broker.subscribe(TOPIC, self._handle_in_memory)
            logger.info("Request consumer subscribed (in-memory)", topic=TOPIC)
            try:
                await self._stopped.wait()
            finally:
                self._broker.unsubscribe(TOPIC, self._handle_in_memory)
            return

        from aiokafka import AIOKafkaConsumer, TopicPartition  # lazy: keeps tests fast

        consumer = AIOKafkaConsumer(
            TOPIC,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # REM-012: manual commit after _handle() completes
        )
        await consumer.start()
        logger.info("Request consumer started", topic=TOPIC)
        try:
            async for msg in consumer:
                if not self._running:
                    break
                await self._handle(msg)
                # Commit only after _handle() finishes (success or DLQ-routed).
                tp = TopicPartition(msg.topic, msg.partition)
                await consumer.commit({tp: msg.offset + 1})
                # REM-013: update liveness timestamp for the ConsumerStale alert.
                CONSUMER_HEARTBEAT_TIMESTAMP.labels(settings.kafka_consumer_group).set(
                    datetime.now(UTC).timestamp()
                )
        finally:
            await consumer.stop()
            logger.info("Request consumer stopped")

    async def stop(self) -> None:
        self._running = False
        self._stopped.set()

    async def _handle_in_memory(self, topic: str, envelope: dict[str, Any]) -> None:
        await self._process(envelope)
        CONSUMER_HEARTBEAT_TIMESTAMP.labels(settings.kafka_consumer_group).set(
            datetime.now(UTC).timestamp()
        )

    async def _handle(self, msg: Any) -> None:
        """Process one Kafka message: parse → idempotency check → orchestrate."""
        try:
            envelope = json.loads(msg.value)
        except Exception as exc:
            logger.error("Failed to parse event from topic", topic=TOPIC, error=str(exc))
            return
        await self._process(envelope)

    # ── core ───────────────────────────────────────────────────────────────────

    def _build_orchestrator(self) -> AgentOrchestrator:
        if self._llm is None:
            # Late import: the factory pulls the OTel wrapper; keep module import light.
            from src.agents.llm_factory import build_llm_client

            self._llm = build_llm_client()
        return AgentOrchestrator(
            agent_id=settings.service_name,
            audit_logger=self._audit,
            hitl_gateway=self._hitl,
            llm_client=self._llm,
        )

    async def _run_agent(
        self, orchestrator: AgentOrchestrator, request_id: str, request_text: str, trace_id: Any
    ) -> dict[str, Any]:
        """Run through the harness when configured, else the bare orchestrator."""
        if self._harness is not None:
            from src.agents.harness.models import TaskBrief

            harness_result = await self._harness.run(
                TaskBrief(task_id=request_id, description=request_text, trace_id=trace_id)
            )
            return {
                "status": "completed",
                "harness_mode": harness_result.mode,
                "iterations": harness_result.total_iterations,
                "escalated_to_hitl": harness_result.escalated_to_hitl,
                "artifacts": [a.outputs for a in harness_result.artifacts],
            }
        result = await orchestrator.run(raw_input={"request_text": request_text}, trace_id=trace_id)
        return result if isinstance(result, dict) else {"output": str(result)}

    async def _process(self, envelope: dict[str, Any]) -> None:
        """Idempotency check → status transitions → orchestrate with retries → DLQ.

        On transient failure: retries up to kafka_consumer_max_retries with exponential
        backoff. On exhaustion: publishes envelope to DLQ topic, increments
        DLQ_MESSAGES_COUNTER, and sets request status to 'failed'.
        """
        if not isinstance(envelope, dict):
            logger.error(
                "Envelope is not an object — skipping", topic=TOPIC, kind=type(envelope).__name__
            )
            return
        payload = envelope.get("payload") or {}
        request_id = payload.get("request_id") if isinstance(payload, dict) else None
        trace_id = envelope.get("trace_id")

        if not request_id:
            logger.warning("Event missing request_id — skipping", topic=TOPIC)
            return

        # Idempotency: skip if already past "queued" (duplicate delivery).
        existing = await self._store.get(request_id)
        if existing is not None and existing.status != "queued":
            logger.info("Skipping duplicate event", request_id=request_id, status=existing.status)
            return

        now = datetime.now(UTC)
        created_at = existing.created_at if existing else now

        # queued → processing
        await self._store.save(
            RequestState(
                request_id=request_id, status="processing", created_at=created_at, updated_at=now
            )
        )

        last_exc: Exception | None = None
        max_retries = settings.kafka_consumer_max_retries
        orchestrator = self._build_orchestrator()  # once per message, not per attempt
        request_text = payload.get("request_text", "")

        for attempt in range(max_retries + 1):
            try:
                if self._semaphore is not None:
                    AGENT_SEMAPHORE_WAITING.labels(settings.service_name).inc()
                    try:
                        async with self._semaphore:
                            AGENT_SEMAPHORE_WAITING.labels(settings.service_name).dec()
                            result = await self._run_agent(
                                orchestrator, request_id, request_text, trace_id
                            )
                    except BaseException:
                        # dec() already ran if we got inside the `with`; otherwise undo the inc().
                        if AGENT_SEMAPHORE_WAITING.labels(settings.service_name)._value.get() > 0:
                            AGENT_SEMAPHORE_WAITING.labels(settings.service_name).dec()
                        raise
                else:
                    result = await self._run_agent(orchestrator, request_id, request_text, trace_id)

                waiting = result.get("status") == STATUS_WAITING
                await self._store.save(
                    RequestState(
                        request_id=request_id,
                        status=STATUS_WAITING if waiting else "completed",
                        created_at=created_at,
                        updated_at=datetime.now(UTC),
                        result=result,
                    )
                )
                logger.info(
                    "Request suspended for HITL" if waiting else "Request completed",
                    request_id=request_id,
                    hitl_request_id=result.get("hitl_request_id") if waiting else None,
                )
                return

            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    backoff = (2**attempt) * settings.kafka_consumer_retry_backoff_seconds
                    logger.warning(
                        "Request processing failed — retrying",
                        request_id=request_id,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        backoff_seconds=backoff,
                        error=str(exc),
                    )
                    await asyncio.sleep(backoff)

        # All retries exhausted — route to DLQ (REM-012).
        error_msg = str(last_exc) if last_exc else "unknown error"
        logger.error(
            "Request failed after all retries — routing to DLQ",
            request_id=request_id,
            attempts=max_retries + 1,
            error=error_msg,
            dlq_topic=settings.kafka_dlq_topic,
            dlq_routed=True,
        )

        dlq_envelope = {**envelope, "dlq_error": error_msg}
        try:
            await self._broker.publish(settings.kafka_dlq_topic, dlq_envelope, key=request_id)
            DLQ_MESSAGES_COUNTER.labels(
                settings.kafka_consumer_group, settings.kafka_dlq_topic
            ).inc()
        except Exception as dlq_exc:
            # DLQ publish failure is critical but must not block the offset commit.
            logger.error(
                "DLQ publish failed — request status set to failed for manual recovery",
                request_id=request_id,
                error=str(dlq_exc),
            )

        await self._store.save(
            RequestState(
                request_id=request_id,
                status="failed",
                created_at=created_at,
                updated_at=datetime.now(UTC),
                error=error_msg,
            )
        )
