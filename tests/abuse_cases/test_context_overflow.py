"""Abuse case tests: context overflow attacks.

Attack vector: an attacker floods the context window with padding tokens to push
spec constraints and system prompt instructions beyond the model's effective context,
causing it to "forget" its permission boundaries.

Mitigation layers tested:
  1. Injection guard: excessive length rejection
  2. Spec contract: validated at validate_action() call, not reliant on in-context instructions
  3. Action schema validator: large payloads rejected at the schema gate

All tests use mock LLMs — no real API calls.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 4 (CV1)
ADR:  ADR-0050
Issue: #35
"""

from __future__ import annotations

import pytest

from src.guardrails.prompt_injection_guard import PromptInjectionGuard, RejectionReason


@pytest.mark.abuse_case
class TestContextOverflowViaInjectionGuard:
    def test_very_long_input_rejected_at_injection_guard(self) -> None:
        """Input exceeding max_input_length is rejected before LLM context injection."""
        guard = PromptInjectionGuard(max_input_length=1000)
        overflow_input = "PADDING_TOKEN " * 500  # 7000 chars
        result = guard.validate(overflow_input)
        assert not result.is_valid
        assert result.rejection_reason == RejectionReason.EXCESSIVE_LENGTH

    def test_repetition_attack_rejected(self) -> None:
        """Repeated identical tokens (context stuffing) are caught by repetition check."""
        guard = PromptInjectionGuard()
        # 60 repetitions of same token — far above repetition threshold
        repetition_input = "TOKEN " * 60
        result = guard.validate(repetition_input)
        assert not result.is_valid


@pytest.mark.abuse_case
class TestContextOverflowViaSpecContract:
    def test_spec_contract_enforcement_is_independent_of_context_size(self) -> None:
        """SpecContractEnforcer validates actions structurally — not via in-context instructions.

        Even if an attacker floods the context to push the [SPEC_CONTRACT] block
        out of the LLM's effective window, validate_action() still checks the
        proposed action against the declared spec.
        """
        from src.agents.spec_contract_enforcer import SpecContractEnforcer, SpecViolationError

        enforcer = SpecContractEnforcer.from_dict(
            {"allowed_action_types": ["read_file", "search_code"]}
        )
        # Regardless of context size, an out-of-scope action is caught
        with pytest.raises(SpecViolationError):
            enforcer.validate_action("delete_database")

    def test_spec_contract_blocks_novel_action_after_overflow_simulation(self) -> None:
        """Simulates the LLM proposing an unexpected action after context overflow."""
        from src.agents.spec_contract_enforcer import SpecContractEnforcer, SpecViolationError

        enforcer = SpecContractEnforcer.from_dict({"allowed_action_types": ["read_file"]})
        # Action that a context-overflowed model might propose
        with pytest.raises(SpecViolationError):
            enforcer.validate_action("execute_shell_command")


@pytest.mark.abuse_case
class TestContextOverflowViaActionSchema:
    def test_oversized_payload_rejected_by_schema_validator(self) -> None:
        """Payloads exceeding the schema max_payload_bytes are rejected."""
        from src.agents.action_schema_validator import ActionSchemaError, ActionSchemaValidator

        validator = ActionSchemaValidator.from_dict(
            {
                "write-db-record": {
                    "required": ["table", "data"],
                    "properties": {"table": {"type": "string"}, "data": {"type": "object"}},
                    "max_payload_bytes": 100,
                }
            }
        )
        oversized_payload = {
            "table": "users",
            "data": {"padding": "X" * 10_000},  # Way over 100 bytes
        }
        with pytest.raises(ActionSchemaError, match="exceeds limit"):
            validator.validate_or_raise("write-db-record", oversized_payload)
