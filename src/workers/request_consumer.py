"""Domain request consumer — reads domain.request.created, drives AgentOrchestrator.

Runs as an asyncio background task in the FastAPI lifespan.

Production note: in a multi-service deployment this worker runs as a separate
process/Deployment, not co-located with the API server. The in-process approach
used here is intentional for self-contained template demonstration.

Spec: specs/system/request-pipeline.md
ADR:  ADR-0003 (Async API Strategy), ADR-0011 (HITL/HOTL Model)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from src.agents.hitl_gateway import HITLGateway
from src.agents.orchestrator.orchestrator import AgentOrchestrator
from src.agents.request_store import RequestState, RequestStoreProtocol
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.shared.config import settings
from src.shared.llm_client import AnthropicLLMClient

logger = get_logger("request_consumer")

TOPIC = "domain.request.created"


class RequestConsumer:
    """Kafka consumer that drives AgentOrchestrator processing for each submitted request.

    Start via asyncio.create_task(consumer.run()) in the FastAPI lifespan.
    Stop by cancelling the task or calling stop() before cancellation.
    """

    def __init__(
        self,
        store: RequestStoreProtocol,
        audit_logger: AuditLogger,
        hitl_gateway: HITLGateway,
    ) -> None:
        self._store = store
        self._audit = audit_logger
        self._hitl = hitl_gateway
        self._running = False

    async def run(self) -> None:
        """Main consume loop. Designed to be started as asyncio.create_task()."""
        from aiokafka import AIOKafkaConsumer  # lazy import — keeps tests fast

        self._running = True
        consumer = AIOKafkaConsumer(
            TOPIC,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await consumer.start()
        logger.info("Request consumer started", topic=TOPIC)
        try:
            async for msg in consumer:
                if not self._running:
                    break
                await self._handle(msg)
        finally:
            await consumer.stop()
            logger.info("Request consumer stopped")

    async def stop(self) -> None:
        self._running = False

    async def _handle(self, msg: Any) -> None:
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

        # Idempotency: skip if already past "queued" (duplicate delivery)
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
        except Exception as exc:
            logger.error("Request processing failed", request_id=request_id, error=str(exc))
            await self._store.save(
                RequestState(
                    request_id=request_id,
                    status="failed",
                    created_at=created_at,
                    updated_at=datetime.now(UTC),
                    error=str(exc),
                )
            )
