"""Unit tests for SpecContractEnforcer.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 1 (SD1)
ADR:  ADR-0047
Issue: #32
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.agents.spec_contract_enforcer import (
    SpecContract,
    SpecContractEnforcer,
    SpecViolationError,
)

# ── SpecContract dataclass ────────────────────────────────────────────────────


class TestSpecContract:
    def test_empty_contract_is_permissive(self) -> None:
        contract = SpecContract()
        assert contract.allowed_action_types == []
        assert contract.prohibited_operations == []
        assert contract.scope_boundary == ""

    def test_allowed_set_is_frozenset(self) -> None:
        contract = SpecContract(allowed_action_types=["read_file", "search_code"])
        assert "read_file" in contract._allowed
        assert "write_file" not in contract._allowed

    def test_prohibited_set_is_frozenset(self) -> None:
        contract = SpecContract(prohibited_operations=["execute_code"])
        assert "execute_code" in contract._prohibited


# ── validate_action ───────────────────────────────────────────────────────────


class TestValidateAction:
    def test_allows_action_in_allowed_list(self) -> None:
        enforcer = SpecContractEnforcer.from_dict(
            {"allowed_action_types": ["read_file", "search_code"]}
        )
        enforcer.validate_action("read_file")  # must not raise

    def test_raises_for_action_not_in_allowed_list(self) -> None:
        enforcer = SpecContractEnforcer.from_dict({"allowed_action_types": ["read_file"]})
        with pytest.raises(SpecViolationError, match="not in the spec contract"):
            enforcer.validate_action("write_file")

    def test_raises_for_explicitly_prohibited_action(self) -> None:
        enforcer = SpecContractEnforcer.from_dict(
            {
                "allowed_action_types": ["read_file", "execute_code"],
                "prohibited_operations": ["execute_code"],
            }
        )
        with pytest.raises(SpecViolationError, match="explicitly prohibited"):
            enforcer.validate_action("execute_code")

    def test_empty_allowed_list_permits_any_action(self) -> None:
        enforcer = SpecContractEnforcer.from_dict({"allowed_action_types": []})
        enforcer.validate_action("any_action")  # must not raise

    def test_prohibited_takes_priority_over_allowed(self) -> None:
        enforcer = SpecContractEnforcer.from_dict(
            {
                "allowed_action_types": ["write_file"],
                "prohibited_operations": ["write_file"],
            }
        )
        with pytest.raises(SpecViolationError, match="explicitly prohibited"):
            enforcer.validate_action("write_file")

    def test_unknown_action_blocked_when_allowed_list_set(self) -> None:
        enforcer = SpecContractEnforcer.from_dict({"allowed_action_types": ["read_file"]})
        with pytest.raises(SpecViolationError):
            enforcer.validate_action("unknown_action")


# ── inject_contract ───────────────────────────────────────────────────────────


class TestInjectContract:
    def test_appends_spec_contract_block(self) -> None:
        enforcer = SpecContractEnforcer.from_dict(
            {
                "allowed_action_types": ["read_file"],
                "prohibited_operations": ["execute_code"],
                "scope_boundary": "Read-only codebase access",
            }
        )
        result = enforcer.inject_contract("Base prompt.")
        assert "[SPEC_CONTRACT]" in result
        assert "[/SPEC_CONTRACT]" in result
        assert "read_file" in result
        assert "execute_code" in result
        assert "Read-only codebase access" in result

    def test_empty_allowed_uses_any(self) -> None:
        enforcer = SpecContractEnforcer.from_dict({})
        result = enforcer.inject_contract("Base.")
        assert "any" in result

    def test_preserves_original_prompt_content(self) -> None:
        enforcer = SpecContractEnforcer.from_dict({})
        result = enforcer.inject_contract("My original prompt text.")
        assert "My original prompt text." in result

    def test_no_scope_boundary_omitted(self) -> None:
        enforcer = SpecContractEnforcer.from_dict({"scope_boundary": ""})
        result = enforcer.inject_contract("Prompt.")
        assert "Scope boundary" not in result


# ── from_yaml factory ─────────────────────────────────────────────────────────


class TestFromYaml:
    def test_loads_yaml_file(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            allowed_action_types:
              - read_file
              - search_code
            prohibited_operations:
              - write_external_api
            scope_boundary: "Local read-only operations."
        """)
        spec_file = tmp_path / "spec_contract.yaml"
        spec_file.write_text(yaml_content)

        enforcer = SpecContractEnforcer.from_yaml(spec_file)
        assert enforcer.contract.allowed_action_types == ["read_file", "search_code"]
        assert enforcer.contract.prohibited_operations == ["write_external_api"]
        assert enforcer.contract.scope_boundary == "Local read-only operations."

    def test_empty_yaml_gives_permissive_contract(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "empty.yaml"
        spec_file.write_text("{}")
        enforcer = SpecContractEnforcer.from_yaml(spec_file)
        assert enforcer.contract.allowed_action_types == []


# ── from_dict factory ─────────────────────────────────────────────────────────


class TestFromDict:
    def test_builds_from_dict(self) -> None:
        enforcer = SpecContractEnforcer.from_dict(
            {
                "allowed_action_types": ["op_a"],
                "prohibited_operations": ["op_b"],
                "scope_boundary": "Test scope",
            }
        )
        assert enforcer.contract.scope_boundary == "Test scope"
        enforcer.validate_action("op_a")  # must not raise

    def test_missing_keys_use_defaults(self) -> None:
        enforcer = SpecContractEnforcer.from_dict({})
        assert enforcer.contract.allowed_action_types == []
