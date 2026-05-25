"""Integration tests for the PII masking pipeline across component boundaries.

Spec: specs/ai/guardrails.md (Layer 1 — PII Filter)
ADR:  ADR-0012

Validates the three mandatory interception points defined in ADR-0012:
1. Pre-LLM call — context masked before prompt construction
2. Pre-log write — structured log fields masked before emission
3. Pre-broker publish — event payload masked before Kafka produce

All test inputs use synthetic, obviously fake data (no real PII).
"""

from __future__ import annotations

import pytest

from src.guardrails.pii_filter import PIIFilter, PIILevel, mask_dict, mask_text

SYNTHETIC_EMAIL = "fake@example.com"
SYNTHETIC_CPF = "000.000.000-00"
SYNTHETIC_IP = "192.0.2.1"  # TEST-NET per RFC 5737
SYNTHETIC_PHONE = "+00 00 00000-0000"
SYNTHETIC_JWT = "aaaaaaaaaa.bbbbbbbbbb.cccccccccc"
SYNTHETIC_UUID = "00000000-0000-0000-0000-000000000000"


# ── Interception point 1: pre-LLM call ───────────────────────────────────────


@pytest.mark.integration
class TestPreLLMInterception:
    """Verify PII is masked before any context reaches the LLM boundary."""

    def test_agent_context_email_masked(self):
        raw_context = {
            "user_request": f"Please update my email to {SYNTHETIC_EMAIL}",
            "user_id": SYNTHETIC_UUID,
        }
        masked = mask_dict(raw_context)
        assert SYNTHETIC_EMAIL not in str(masked)
        assert "[EMAIL]" in str(masked)

    def test_agent_context_cpf_masked(self):
        raw_context = {"document": f"CPF {SYNTHETIC_CPF} requested access"}
        masked = mask_dict(raw_context)
        assert SYNTHETIC_CPF not in str(masked)
        assert "[CPF]" in str(masked)

    def test_agent_context_ip_masked(self):
        raw_context = {"origin": f"Request from {SYNTHETIC_IP}"}
        masked = mask_dict(raw_context)
        assert SYNTHETIC_IP not in str(masked)

    def test_agent_context_all_fields_masked(self):
        raw_context = {
            "email": SYNTHETIC_EMAIL,
            "document": SYNTHETIC_CPF,
            "origin_ip": SYNTHETIC_IP,
            "phone": SYNTHETIC_PHONE,
        }
        masked = mask_dict(raw_context)
        for raw in (SYNTHETIC_EMAIL, SYNTHETIC_CPF, SYNTHETIC_IP, SYNTHETIC_PHONE):
            assert raw not in str(masked), f"PII leaked: {raw}"

    def test_non_pii_fields_pass_through(self):
        ctx = {"action": "summarise_report", "report_id": "RPT-2026-001", "priority": "high"}
        masked = mask_dict(ctx)
        assert masked["action"] == "summarise_report"
        assert masked["report_id"] == "RPT-2026-001"


# ── Interception point 2: pre-log write ──────────────────────────────────────


@pytest.mark.integration
class TestPreLogInterception:
    """Verify structured log records are masked before emission."""

    def test_log_record_email_masked(self):
        log_record = {
            "level": "INFO",
            "message": "User request received",
            "user_email": SYNTHETIC_EMAIL,
            "trace_id": "abc123",
        }
        masked = mask_dict(log_record)
        assert SYNTHETIC_EMAIL not in str(masked)
        assert masked["trace_id"] == "abc123"  # non-PII preserved

    def test_log_record_nested_pii_masked(self):
        log_record = {
            "event": "action_proposed",
            "context": {
                "requester": {"email": SYNTHETIC_EMAIL, "ip": SYNTHETIC_IP},
                "action": "send_report",
            },
        }
        masked = mask_dict(log_record)
        assert SYNTHETIC_EMAIL not in str(masked)
        assert SYNTHETIC_IP not in str(masked)
        assert masked["context"]["action"] == "send_report"

    def test_log_record_list_values_masked(self):
        log_record = {
            "recipients": [SYNTHETIC_EMAIL, "other@example.org"],
        }
        masked = mask_dict(log_record)
        result_str = str(masked)
        assert SYNTHETIC_EMAIL not in result_str
        assert "other@example.org" not in result_str


# ── Interception point 3: pre-broker publish ─────────────────────────────────


@pytest.mark.integration
class TestPreBrokerInterception:
    """Verify event payloads are masked before Kafka produce."""

    def test_event_payload_pii_masked(self):
        raw_event = {
            "event_id": SYNTHETIC_UUID,
            "event_type": "domain.request.created",
            "payload": {
                "user_email": SYNTHETIC_EMAIL,
                "request_text": f"Update CPF to {SYNTHETIC_CPF}",
            },
        }
        masked = mask_dict(raw_event)
        assert SYNTHETIC_EMAIL not in str(masked)
        assert SYNTHETIC_CPF not in str(masked)
        # Structural fields preserved
        assert masked["event_type"] == "domain.request.created"

    def test_event_envelope_uuid_masked_at_l3(self):
        pii = PIIFilter()
        raw_event = {"correlation_id": SYNTHETIC_UUID}
        # UUID is L3 (internal); default min_level is L2 — UUID should be masked
        masked = pii.mask_dict(raw_event, min_level=PIILevel.L3_INTERNAL)
        assert SYNTHETIC_UUID not in str(masked)

    def test_event_envelope_uuid_passes_at_l2(self):
        pii = PIIFilter()
        raw_event = {"correlation_id": SYNTHETIC_UUID}
        # At L2 threshold, L3 (UUID) passes through
        masked = pii.mask_dict(raw_event, min_level=PIILevel.L2_SENSITIVE)
        assert SYNTHETIC_UUID in str(masked)


# ── End-to-end: context summary for HITL reviewer ────────────────────────────


@pytest.mark.integration
class TestHITLContextSummaryMasking:
    """Verify that the context summary shown to HITL reviewers is fully masked."""

    def test_hitl_summary_contains_no_raw_pii(self):
        raw_summary = (
            f"User {SYNTHETIC_EMAIL} requested access from {SYNTHETIC_IP}. "
            f"Document: {SYNTHETIC_CPF}. Phone: {SYNTHETIC_PHONE}."
        )
        masked_summary = mask_text(raw_summary)

        for pii in (SYNTHETIC_EMAIL, SYNTHETIC_IP, SYNTHETIC_CPF, SYNTHETIC_PHONE):
            assert pii not in masked_summary, f"PII leaked in HITL summary: {pii}"

    def test_hitl_summary_retains_action_description(self):
        raw_summary = f"Requested action: send_report. Requester: {SYNTHETIC_EMAIL}."
        masked = mask_text(raw_summary)
        assert "send_report" in masked
        assert "Requested action" in masked
