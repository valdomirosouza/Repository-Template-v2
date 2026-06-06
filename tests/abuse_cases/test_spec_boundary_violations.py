"""Abuse case tests: spec boundary violations.

Attack vector: the LLM proposes an action outside its declared spec scope —
either due to prompt injection, model drift, or a hallucinated capability.

SpecContractEnforcer validates each proposed action against the spec's
allowed_action_types and prohibited_operations before it reaches HITLGateway.

All tests use mock LLMs — no real API calls.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 4 (CV1)
ADR:  ADR-0050
Issue: #35
"""

from __future__ import annotations

import pytest

from src.agents.spec_contract_enforcer import (
    SpecContractEnforcer,
    SpecViolationError,
)


@pytest.mark.abuse_case
class TestSpecBoundaryViolations:
    def test_prohibited_action_rejected(self) -> None:
        """An action listed as prohibited is blocked regardless of the allowed list."""
        enforcer = SpecContractEnforcer.from_dict(
            {
                "allowed_action_types": ["read_file", "execute_code"],
                "prohibited_operations": ["execute_code"],
            }
        )
        with pytest.raises(SpecViolationError, match="explicitly prohibited"):
            enforcer.validate_action("execute_code")

    def test_action_not_in_allowed_list_blocked(self) -> None:
        """An action not in allowed_action_types is blocked when a positive list is declared."""
        enforcer = SpecContractEnforcer.from_dict(
            {"allowed_action_types": ["read_file", "search_code"]}
        )
        with pytest.raises(SpecViolationError, match="not in the spec contract"):
            enforcer.validate_action("delete_all_records")

    def test_hallucinated_capability_blocked(self) -> None:
        """A capability that the LLM hallucinated (not in spec) is blocked."""
        enforcer = SpecContractEnforcer.from_dict(
            {"allowed_action_types": ["read_file", "search_code"]}
        )
        # LLM hallucinates it can call an external API
        with pytest.raises(SpecViolationError):
            enforcer.validate_action("call_external_payment_api")

    def test_drift_to_destructive_action_blocked(self) -> None:
        """A model drifting toward destructive actions is caught by spec enforcement."""
        enforcer = SpecContractEnforcer.from_dict(
            {
                "allowed_action_types": ["read_file"],
                "prohibited_operations": ["delete_file", "format_disk"],
            }
        )
        with pytest.raises(SpecViolationError):
            enforcer.validate_action("delete_file")

    def test_allowed_action_passes(self) -> None:
        """A legitimately declared action passes spec enforcement."""
        enforcer = SpecContractEnforcer.from_dict(
            {"allowed_action_types": ["read_file", "search_code", "summarise"]}
        )
        enforcer.validate_action("read_file")  # must not raise

    def test_spec_contract_injected_into_system_prompt(self) -> None:
        """The [SPEC_CONTRACT] block is injected into the system prompt."""
        enforcer = SpecContractEnforcer.from_dict(
            {
                "allowed_action_types": ["read_file"],
                "prohibited_operations": ["delete_database"],
                "scope_boundary": "Read-only local filesystem access",
            }
        )
        prompt = enforcer.inject_contract("You are an AI agent.")
        assert "[SPEC_CONTRACT]" in prompt
        assert "read_file" in prompt
        assert "delete_database" in prompt
        assert "Read-only local filesystem access" in prompt

    def test_empty_spec_allows_any_action(self) -> None:
        """A permissive spec (no allowed list, no prohibited ops) allows all actions."""
        enforcer = SpecContractEnforcer.from_dict({})
        enforcer.validate_action("any_action")  # must not raise

    def test_schema_validator_rejects_malformed_payload(self) -> None:
        """An action that passes spec enforcement can still be blocked by schema validation."""
        from src.agents.action_schema_validator import ActionSchemaError, ActionSchemaValidator

        # Even a spec-allowed action with a malformed payload is rejected
        validator = ActionSchemaValidator.from_dict(
            {
                "write-db-record": {
                    "required": ["table", "data"],
                    "properties": {
                        "table": {"type": "string"},
                        "data": {"type": "object"},
                    },
                }
            }
        )
        # Missing required field 'data'
        with pytest.raises(ActionSchemaError, match="Missing required field"):
            validator.validate_or_raise("write-db-record", {"table": "users"})
