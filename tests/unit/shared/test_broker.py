"""Unit tests for src/shared/broker — event envelope and InMemoryBroker.

Spec: specs/system/request-pipeline.md, specs/api/async-api-design.md
ADR:  ADR-0003 (Async API Strategy), ADR-0005 (Message Broker Selection)

No Kafka or Redis required — all tests use InMemoryBroker.
All test inputs use clearly synthetic, obviously fake data.
"""

from __future__ import annotations

import uuid

import pytest

from src.guardrails.pii_filter import mask_dict
from src.shared.broker import InMemoryBroker, build_envelope

SYNTHETIC_EMAIL = "fake@example.com"
SYNTHETIC_CPF = "000.000.000-00"

REQUIRED_ENVELOPE_FIELDS = {
    "event_id",
    "event_type",
    "schema_version",
    "produced_at",
    "trace_id",
    "producer_service",
    "payload",
}


# ── build_envelope ────────────────────────────────────────────────────────────


def test_build_envelope_has_all_required_fields() -> None:
    envelope = build_envelope("domain.request.created", {"request_id": "req-001"})
    missing = REQUIRED_ENVELOPE_FIELDS - set(envelope.keys())
    assert not missing, f"Envelope missing required fields: {missing}"


def test_build_envelope_event_id_is_uuid_v4() -> None:
    envelope = build_envelope("domain.request.created", {})
    parsed = uuid.UUID(envelope["event_id"])
    assert parsed.version == 4


def test_build_envelope_pii_masked_before_use() -> None:
    raw = {"request_text": f"User {SYNTHETIC_EMAIL} CPF {SYNTHETIC_CPF}"}
    safe = mask_dict(raw)
    envelope = build_envelope("domain.request.created", safe)
    serialised = str(envelope)
    assert SYNTHETIC_EMAIL not in serialised
    assert SYNTHETIC_CPF not in serialised
    assert "[EMAIL]" in serialised
    assert "[CPF]" in serialised


# ── InMemoryBroker ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_in_memory_broker_captures_published_events() -> None:
    broker = InMemoryBroker()
    await broker.publish("domain.request.created", {"event_id": "e-1"})
    await broker.publish("domain.request.created", {"event_id": "e-2"})
    assert len(broker.published) == 2


@pytest.mark.asyncio
async def test_in_memory_broker_stores_topic_and_payload() -> None:
    broker = InMemoryBroker()
    payload = {"event_id": "e-test", "event_type": "domain.request.created"}
    await broker.publish("domain.request.created", payload, key="req-123")
    captured = broker.published[0]
    assert captured["topic"] == "domain.request.created"
    assert captured["payload"]["event_id"] == "e-test"
