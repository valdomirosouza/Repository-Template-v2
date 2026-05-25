"""Defensive validation suite for OWASP LLM Top 10 guardrail coverage.

Spec: specs/ai/guardrails.md (Layers 1-4)
ADR:  ADR-0010 (Agent Framework), ADR-0011 (HITL/HOTL), ADR-0012 (PII Masking)

Each test verifies that the relevant guardrail REJECTS a synthetic
placeholder input representing a risk category. No real exploit payloads
are stored in this file.

Risk categories tested by name:
  LLM01 - Input manipulation attempts (structural anomaly detection)
  LLM06 - PII exposure prevention (masking before LLM call)
  LLM08 - Excessive agency prevention (action scope limits)
  LLM09 - Audit log integrity (immutable write enforcement)
"""

import pytest

from src.guardrails.action_limits import ActionLimitConfig, ActionLimiter
from src.guardrails.pii_filter import PIIFilter
from src.guardrails.prompt_injection_guard import PromptInjectionGuard, RejectionReason


class TestLLM01_InputManipulationPrevention:
    """Verify guard rejects structurally anomalous inputs (LLM01 category)."""

    def test_high_repetition_rejected(self):
        guard = PromptInjectionGuard()
        synthetic = "SYNTHETIC_INJECT_ATTEMPT " * 60
        result = guard.validate(synthetic)
        assert not result.is_valid, "Guard must reject high-repetition synthetic input"

    def test_excessive_length_rejected(self):
        guard = PromptInjectionGuard(max_input_length=500)
        long_synthetic = "SYNTHETIC_PADDING_TOKEN " * 100
        result = guard.validate(long_synthetic)
        assert not result.is_valid
        assert result.rejection_reason == RejectionReason.EXCESSIVE_LENGTH

    def test_normal_input_accepted(self):
        guard = PromptInjectionGuard()
        result = guard.validate("Please summarise the latest report.")
        assert result.is_valid

    def test_synthetic_override_pattern_risk_elevated(self):
        guard = PromptInjectionGuard()
        synthetic = "SYNTHETIC_OVERRIDE_TOKEN: " * 15
        result = guard.validate(synthetic)
        assert result.risk_score > 0.3, "Structural anomaly should elevate risk score"

    def test_result_is_never_none(self):
        guard = PromptInjectionGuard()
        result = guard.validate("TEST_JAILBREAK_PATTERN " * 5)
        assert result is not None


class TestLLM06_PIIExposurePrevention:
    """Verify PII is masked before reaching LLM boundary (LLM06 category)."""

    def test_email_masked_before_llm(self):
        pii = PIIFilter()
        raw = "User email is fake@example.com"
        masked = pii.mask_text(raw)
        assert "fake@example.com" not in masked
        assert "[EMAIL]" in masked

    def test_cpf_masked_before_llm(self):
        pii = PIIFilter()
        # All-zero CPF — clearly synthetic, not a real person
        raw = "Document: 000.000.000-00"
        masked = pii.mask_text(raw)
        assert "000.000.000-00" not in masked
        assert "[CPF]" in masked

    def test_ip_masked_before_llm(self):
        pii = PIIFilter()
        raw = "Origin: 192.0.2.1"  # TEST-NET per RFC 5737
        masked = pii.mask_text(raw)
        assert "192.0.2.1" not in masked

    def test_clean_text_passes_through_unchanged(self):
        pii = PIIFilter()
        raw = "The request completed successfully."
        assert pii.mask_text(raw) == raw

    def test_dict_with_multiple_pii_fields_all_masked(self):
        pii = PIIFilter()
        data = {
            "email": "fake@example.com",
            "ip": "192.0.2.1",
            "role": "analyst",
        }
        result = pii.mask_dict(data)
        assert "fake@example.com" not in str(result)
        assert "192.0.2.1" not in str(result)
        assert result["role"] == "analyst"


class TestLLM08_ExcessiveAgencyPrevention:
    """Verify action scope limits block out-of-scope agent actions (LLM08 category)."""

    def test_disallowed_action_type_rejected(self):
        config = ActionLimitConfig(
            agent_id="test-agent",
            max_actions_per_minute=10,
            max_actions_per_hour=100,
            allowed_action_types=["read_document", "summarise"],
            max_records_affected=10,
            allowed_environments=["staging"],
        )
        limiter = ActionLimiter(config=config, redis_client=None)
        allowed, reason = limiter.check_scope_limit(
            agent_id="test-agent",
            action_type="delete_all_records",
            parameters={},
        )
        assert not allowed
        assert reason  # reason must be non-empty

    def test_allowed_action_type_passes(self):
        config = ActionLimitConfig(
            agent_id="test-agent",
            max_actions_per_minute=10,
            max_actions_per_hour=100,
            allowed_action_types=["read_document"],
            max_records_affected=10,
            allowed_environments=["staging"],
        )
        limiter = ActionLimiter(config=config, redis_client=None)
        allowed, _ = limiter.check_scope_limit(
            agent_id="test-agent",
            action_type="read_document",
            parameters={},
        )
        assert allowed

    def test_bulk_operation_exceeding_limit_rejected(self):
        config = ActionLimitConfig(
            agent_id="test-agent",
            max_actions_per_minute=10,
            max_actions_per_hour=100,
            allowed_action_types=["update_records"],
            max_records_affected=5,
            allowed_environments=["staging"],
        )
        limiter = ActionLimiter(config=config, redis_client=None)
        allowed, _reason = limiter.check_scope_limit(
            agent_id="test-agent",
            action_type="update_records",
            parameters={"record_count": 100},
        )
        assert not allowed

    def test_empty_allowed_list_permits_all_types(self):
        config = ActionLimitConfig(
            agent_id="test-agent",
            max_actions_per_minute=10,
            max_actions_per_hour=100,
            allowed_action_types=[],  # empty = no restriction
            max_records_affected=100,
            allowed_environments=["staging"],
        )
        limiter = ActionLimiter(config=config, redis_client=None)
        allowed, _ = limiter.check_scope_limit(
            agent_id="test-agent",
            action_type="anything",
            parameters={},
        )
        assert allowed


class TestLLM09_AuditLogIntegrity:
    """Verify audit logger enforces write integrity (LLM09 category)."""

    @pytest.mark.asyncio
    async def test_audit_event_persisted(self):
        from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
        from src.shared.models import AuditEvent

        storage = InMemoryAuditStorage()
        audit = AuditLogger(storage_backend=storage)
        event = AuditEvent(
            event_type="agent_action",
            agent_id="test-agent",
            action="read_document",
            outcome="success",
        )
        event_id = await audit.log_event(event)
        assert event_id is not None
        events = await audit.query_events(agent_id="test-agent")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_failed_write_raises_error(self):
        from src.guardrails.audit_logger import AuditLogger, AuditWriteError
        from src.shared.models import AuditEvent

        class FailingStorage:
            async def append(self, event: object) -> None:
                raise RuntimeError("Storage unavailable")

            async def query(self, **kwargs: object) -> list:
                return []

        audit = AuditLogger(storage_backend=FailingStorage())
        event = AuditEvent(
            event_type="agent_action",
            agent_id="test-agent",
            action="write_record",
            outcome="pending",
        )
        with pytest.raises(AuditWriteError):
            await audit.log_event(event)

    @pytest.mark.asyncio
    async def test_multiple_events_all_persisted(self):
        from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
        from src.shared.models import AuditEvent

        storage = InMemoryAuditStorage()
        audit = AuditLogger(storage_backend=storage)
        for i in range(5):
            await audit.log_event(
                AuditEvent(
                    event_type="agent_action",
                    agent_id="test-agent",
                    action=f"action_{i}",
                    outcome="success",
                )
            )
        events = await audit.query_events(agent_id="test-agent")
        assert len(events) == 5
