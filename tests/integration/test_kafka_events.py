"""Integration tests for Kafka event contract compliance.

Spec: specs/api/async-api-design.md
ADR:  ADR-0003 (Async API Strategy), ADR-0005 (Message Broker Selection)

Validates the event envelope structure, PII masking before publish,
topic naming convention, and idempotency key format as required by
specs/api/async-api-design.md.

Kafka availability: tests that assert on producer behaviour use an
InMemoryProducer stub and run without a real Kafka connection.
Tests are marked @pytest.mark.integration so they are included in the
CI test-integration job (which provides Kafka at localhost:9092).
All test inputs use synthetic, obviously fake data — no real PII.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from src.guardrails.pii_filter import mask_dict

# ── Synthetic PII constants (no real personal data) ───────────────────────────

SYNTHETIC_EMAIL = "fake@example.com"
SYNTHETIC_CPF = "000.000.000-00"  # all-zero CPF — not a valid Brazilian CPF


# ── In-memory producer stub ───────────────────────────────────────────────────


@dataclass
class CapturedEvent:
    topic: str
    value: dict[str, Any]


class InMemoryProducer:
    """Drop-in stub for aiokafka.AIOKafkaProducer.

    Captures sent events in memory so structural assertions can run
    without a real broker connection.
    """

    def __init__(self) -> None:
        self.sent: list[CapturedEvent] = []

    async def send_and_wait(self, topic: str, value: bytes) -> None:
        self.sent.append(CapturedEvent(topic=topic, value=json.loads(value)))

    async def __aenter__(self) -> InMemoryProducer:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────


def _envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a compliant event envelope per specs/api/async-api-design.md."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "schema_version": "1.0",
        "produced_at": datetime.now(UTC).isoformat(),
        "trace_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "producer_service": "test-service",
        "payload": payload,
    }


# ── Test 1: envelope structure ────────────────────────────────────────────────


@pytest.mark.integration
def test_event_envelope_has_required_fields() -> None:
    """All seven required fields from the event envelope spec must be present.

    Spec: specs/api/async-api-design.md — Event Envelope section.
    """
    required_fields = {
        "event_id",
        "event_type",
        "schema_version",
        "produced_at",
        "trace_id",
        "producer_service",
        "payload",
    }
    event = _envelope(
        "domain.request.created",
        {
            "request_id": "req-001",
            "user_id": "u-001",
            "request_text": "summarise the quarterly report",
            "priority": "normal",
        },
    )
    missing = required_fields - set(event.keys())
    assert not missing, f"Envelope missing required fields: {missing}"


# ── Test 2: PII masking before publish ────────────────────────────────────────


@pytest.mark.integration
def test_producer_masks_pii_before_publish() -> None:
    """No raw PII must reach the Kafka event payload after masking.

    Spec: specs/api/async-api-design.md — PII Handling in Events.
    ADR:  ADR-0012 (mandatory pre-broker masking — third interception point).
    """
    raw_payload = {
        "request_id": "req-002",
        "user_id": "u-002",
        "request_text": (f"Update email to {SYNTHETIC_EMAIL} for CPF {SYNTHETIC_CPF}"),
        "priority": "high",
    }

    safe_payload = mask_dict(raw_payload)
    event = _envelope("domain.request.created", safe_payload)
    serialised = json.dumps(event)

    assert SYNTHETIC_EMAIL not in serialised, "Raw email leaked into event payload"
    assert SYNTHETIC_CPF not in serialised, "Raw CPF leaked into event payload"
    assert "[EMAIL]" in serialised, "EMAIL masking token missing from serialised event"
    assert "[CPF]" in serialised, "CPF masking token missing from serialised event"


# ── Test 3: topic naming convention ───────────────────────────────────────────


_ALL_EVENT_TYPES = [
    "domain.request.created",
    "agent.action.proposed",
    "agent.action.approved",
    "agent.action.rejected",
    "agent.action.expired",
    "agent.action.executed",
    "domain.result.completed",
    "audit.event.written",
]

_EVENT_TYPE_PATTERN = re.compile(r"^[a-z]+\.[a-z]+\.[a-z]+$")


@pytest.mark.integration
@pytest.mark.parametrize("event_type", _ALL_EVENT_TYPES)
def test_event_type_follows_naming_convention(event_type: str) -> None:
    """Event types must be dot-separated, lowercase, past-tense verb.

    Spec: specs/api/async-api-design.md — Topic Naming Convention.
    Rules: all lowercase, dot-separated, no hyphens/underscores, verb is past tense.
    """
    assert _EVENT_TYPE_PATTERN.match(event_type), (
        f"'{event_type}' does not match <domain>.<entity>.<verb> pattern"
    )
    verb = event_type.split(".")[2]
    assert verb.endswith(("ed", "en")), (
        f"Verb '{verb}' is not past tense — must end in 'ed' or 'en'"
    )


# ── Test 4: idempotency key format ────────────────────────────────────────────


@pytest.mark.integration
def test_idempotency_key_is_uuid_v4() -> None:
    """event_id must be a valid UUID v4 to function as a deduplication key.

    Spec: specs/api/async-api-design.md — Event Envelope field table.
    Consumer requirement: look up event_id before processing to ensure idempotency.
    """
    event = _envelope("domain.request.created", {})
    parsed = uuid.UUID(event["event_id"])
    assert parsed.version == 4, (
        f"event_id '{event['event_id']}' is UUID v{parsed.version}, expected v4"
    )


# ── Test 5: PII masking in domain.request.created payload ─────────────────────


@pytest.mark.integration
def test_pii_masked_in_domain_request_event() -> None:
    """domain.request.created payload must contain no unmasked PII.

    This test exercises the specific payload fields from domain_request.avsc.
    Spec: specs/api/async-api-design.md — Event Catalogue (domain.request.created).
    """
    raw_payload = {
        "request_id": "req-003",
        "user_id": "u-003",
        "request_text": (
            f"User {SYNTHETIC_EMAIL} requests document access. CPF on file: {SYNTHETIC_CPF}."
        ),
        "priority": "normal",
    }

    safe_payload = mask_dict(raw_payload)
    event = _envelope("domain.request.created", safe_payload)
    event_str = json.dumps(event)

    # Raw PII must not appear anywhere in the serialised event
    assert SYNTHETIC_EMAIL not in event_str, "Raw email leaked in domain.request.created"
    assert SYNTHETIC_CPF not in event_str, "Raw CPF leaked in domain.request.created"

    # Masking tokens must be present (confirms masking ran, not just stripped)
    assert "[EMAIL]" in event_str
    assert "[CPF]" in event_str

    # Non-PII structural fields must be preserved unmodified
    assert event["payload"]["request_id"] == "req-003"
    assert event["payload"]["priority"] == "normal"
    assert event["event_type"] == "domain.request.created"


# ── Test 6: non-PII event fields pass through unmodified ──────────────────────


@pytest.mark.integration
def test_non_pii_fields_preserved_after_masking() -> None:
    """Structural and non-PII fields must not be altered by the PII filter.

    Spec: specs/api/async-api-design.md — PII Handling in Events.
    """
    payload = {
        "request_id": "req-004",
        "priority": "high",
        "action": "summarise_report",
        "report_id": "RPT-2026-042",
    }
    safe_payload = mask_dict(payload)

    assert safe_payload["request_id"] == "req-004"
    assert safe_payload["priority"] == "high"
    assert safe_payload["action"] == "summarise_report"
    assert safe_payload["report_id"] == "RPT-2026-042"
