"""Event broker abstraction — Kafka producer and in-memory stub for tests.

All event payloads must be PII-masked by the caller before passing to publish().
build_envelope() constructs the mandatory 7-field envelope per the event contract.

Spec: specs/system/request-pipeline.md, specs/api/async-api-design.md
ADR:  ADR-0003 (Async API Strategy), ADR-0005 (Message Broker Selection)
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from src.observability.logger import get_logger
from src.shared.config import settings

logger = get_logger("broker")


def build_envelope(
    event_type: str,
    payload: dict[str, Any],
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Build a compliant 7-field event envelope per specs/api/async-api-design.md."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "schema_version": "1.0",
        "produced_at": datetime.now(UTC).isoformat(),
        "trace_id": trace_id or "",
        "producer_service": settings.service_name,
        "payload": payload,
    }


Handler = Callable[[str, dict[str, Any]], Awaitable[None]]


class EventBrokerProtocol(Protocol):
    """Structural protocol satisfied by both KafkaEventBroker and InMemoryBroker."""

    async def publish(
        self, topic: str, payload: dict[str, Any], key: str | None = None
    ) -> None: ...


class InMemoryBroker:
    """Kafka fallback — captures published events in memory and dispatches to subscribers.

    Used when Kafka is unreachable (local dev, tests). Since W12 (issue #355) it also carries
    subscriptions, so the request and approval consumers work end-to-end in-process instead of
    silently doing nothing: ``subscribe(topic, handler)`` registers an async handler that is
    awaited on every ``publish`` to that topic. Handler exceptions are logged, never propagated
    to the publisher (a consumer bug must not break the API request that emitted the event).
    """

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self._subscribers: dict[str, list[Handler]] = {}

    async def start(self) -> None:
        """No-op: the in-memory broker needs no connection setup."""

    async def stop(self) -> None:
        """No-op: the in-memory broker needs no teardown."""

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers.setdefault(topic, []).append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, topic: str, payload: dict[str, Any], key: str | None = None) -> None:
        self.published.append({"topic": topic, "payload": payload})
        for handler in list(self._subscribers.get(topic, [])):
            try:
                await handler(topic, payload)
            except Exception as exc:
                logger.error("In-memory subscriber failed", topic=topic, error=str(exc))


class KafkaEventBroker:
    """Wraps aiokafka.AIOKafkaProducer.

    Call start() during FastAPI lifespan startup and stop() on shutdown.
    aiokafka is imported lazily so unit tests never import it.
    """

    def __init__(self, bootstrap_servers: str) -> None:
        self._bootstrap = bootstrap_servers
        self._producer: Any = None

    async def start(self) -> None:
        from aiokafka import AIOKafkaProducer  # lazy: keeps tests fast

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap,
            acks="all",
            enable_idempotence=True,
        )
        await self._producer.start()
        logger.info("Kafka producer started", bootstrap_servers=self._bootstrap)

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def publish(self, topic: str, payload: dict[str, Any], key: str | None = None) -> None:
        if self._producer is None:
            raise RuntimeError("KafkaEventBroker not started — call start() first")
        value = json.dumps(payload).encode()
        key_bytes = key.encode() if key else None
        await self._producer.send_and_wait(topic, value=value, key=key_bytes)
        logger.debug("Event published", topic=topic, event_type=payload.get("event_type"))
