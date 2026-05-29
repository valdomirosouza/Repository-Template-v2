"""Domain request consumer — reads domain.request.created, drives AgentOrchestrator.

Runs as an asyncio background task in the FastAPI lifespan.

Production note: in a multi-service deployment this worker runs as a separate
process/Deployment, not co-located with the API server. The in-process approach
used here is intentional for self-contained template demonstration.

Spec: specs/system/request-pipeline.md
ADR:  ADR-0003 (Async API Strategy), ADR-0011 (HITL/HOTL Model)
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
from src.observability.metrics import CONSUMER_HEARTBEAT_TIMESTAMP, DLQ_MESSAGES_COUNTER
from src.shared.config import settings
from src.shared.llm_client import AnthropicLLMClient

if TYPE_CHECKING:
    from src.shared.broker import EventBrokerProtocol

logger = get_logger("request_consumer")

TOPIC = "domain.request.created"


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
    ) -> None:
        self._store = store
        self._audit = audit_logger
        self._hitl = hitl_gateway
        self._broker = broker
        self._running = False

    async def run(self) -> None:
        """Main consume loop. Designed to be started as asyncio.create_task()."""
        from aiokafka import AIOKafkaConsumer, TopicPartition  # lazy: keeps tests fast

        self._running = True
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
                # Committing here — not inside _handle() — keeps Kafka plumbing out of
                # business logic and simplifies testing.
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

    async def _handle(self, msg: Any) -> None:
        """Process one Kafka message: parse → idempotency check → orchestrate.

        On transient failure: retries up to kafka_consumer_max_retries with exponential
        backoff. On exhaustion: publishes envelope to DLQ topic, increments
        DLQ_MESSAGES_COUNTER, and sets request status to 'failed'. The caller commits
        the offset regardless of outcome.
        """
        try:
            envelope = json.loads(msg.value)
            payload = envelope.get("payload", {})
            request_id = payload.get("request_id")
            trace_id = envelope.get("trace_id")
        except Exception as exc:
            logger.error("Failed to parse event from topic", topic=TOPIC, error=str(exc))
            return

        if not request_id:
            logger.warning("Event missing request_id — skipping", topic=TOPIC)
            return

        # Idempotency: skip if already past "queued" (duplicate delivery).
        existing = await self._store.get(request_id)
        if existing is not None and existing.status != "queued":
            logger.info(
                "Skipping duplicate event",
                request_id=request_id,
                status=existing.status,
            )
            return

        now = datetime.now(UTC)
        created_at = existing.created_at if existing else now

        # queued → processing
        await self._store.save(
            RequestState(
                request_id=request_id,
                status="processing",
                created_at=created_at,
                updated_at=now,
            )
        )

        last_exc: Exception | None = None
        max_retries = settings.kafka_consumer_max_retries

        for attempt in range(max_retries + 1):
            try:
                llm = AnthropicLLMClient()
                orchestrator = AgentOrchestrator(
                    agent_id=settings.service_name,
                    audit_logger=self._audit,
                    hitl_gateway=self._hitl,
                    llm_client=llm,
                )
                result = await orchestrator.run(
                    raw_input={"request_text": payload.get("request_text", "")},
                    trace_id=trace_id,
                )
                await self._store.save(
                    RequestState(
                        request_id=request_id,
                        status="completed",
                        created_at=created_at,
                        updated_at=datetime.now(UTC),
                        result=result if isinstance(result, dict) else {"output": str(result)},
                    )
                )
                logger.info("Request completed", request_id=request_id)
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
            await self._broker.publish(
                settings.kafka_dlq_topic,
                dlq_envelope,
                key=request_id,
            )
            DLQ_MESSAGES_COUNTER.labels(
                settings.kafka_consumer_group, settings.kafka_dlq_topic
            ).inc()
        except Exception as dlq_exc:
            # DLQ publish failure is critical but must not block the offset commit.
            # The request status is still set to 'failed' so operators can detect and replay.
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
