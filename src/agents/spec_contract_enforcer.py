"""Runtime spec contract enforcement for agent actions.

Every agent invocation operates within a declared spec contract. This module:
  1. Loads the contract (allowed_action_types, prohibited_operations, scope_boundary)
  2. Injects a [SPEC_CONTRACT] block into the LLM system prompt so the model
     cannot claim ignorance of its permission boundary.
  3. Validates each proposed action BEFORE it reaches HITLGateway or tool execution.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 1 (SD1)
ADR:  ADR-0047
Issue: #32
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.observability.logger import get_logger

logger = get_logger("spec_contract_enforcer")


class SpecViolationError(Exception):
    """Raised when a proposed agent action falls outside the spec contract."""


@dataclass(frozen=True)
class SpecContract:
    """Immutable spec contract parsed from a YAML sidecar or provided inline."""

    allowed_action_types: list[str] = field(default_factory=list)
    prohibited_operations: list[str] = field(default_factory=list)
    scope_boundary: str = ""

    def __post_init__(self) -> None:
        # Normalize to frozensets internally for O(1) lookup — but keep lists for
        # serialization compatibility (dataclass is frozen so we use object.__setattr__).
        object.__setattr__(self, "_allowed_set", frozenset(self.allowed_action_types))
        object.__setattr__(self, "_prohibited_set", frozenset(self.prohibited_operations))

    @property
    def _allowed(self) -> frozenset[str]:
        return object.__getattribute__(self, "_allowed_set")  # type: ignore[no-any-return]

    @property
    def _prohibited(self) -> frozenset[str]:
        return object.__getattribute__(self, "_prohibited_set")  # type: ignore[no-any-return]


class SpecContractEnforcer:
    """Validates proposed agent actions against the declared spec contract.

    Usage::

        enforcer = SpecContractEnforcer(contract)
        system_prompt = enforcer.inject_contract(base_system_prompt)
        # ... LLM call ...
        enforcer.validate_action(proposed_action_type)  # raises SpecViolationError if out-of-scope
    """

    def __init__(self, contract: SpecContract) -> None:
        self._contract = contract

    # ── Factory methods ───────────────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: Path) -> SpecContractEnforcer:
        """Load a spec contract from a YAML sidecar file.

        Expected YAML structure::

            allowed_action_types:
              - read_file
              - search_code
            prohibited_operations:
              - write_to_external_api_without_hitl
              - execute_code_without_sandbox
            scope_boundary: "Read-only operations on the local codebase."
        """
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        contract = SpecContract(
            allowed_action_types=raw.get("allowed_action_types", []),
            prohibited_operations=raw.get("prohibited_operations", []),
            scope_boundary=raw.get("scope_boundary", ""),
        )
        logger.info(
            "spec_contract.loaded",
            path=str(path),
            allowed_count=len(contract.allowed_action_types),
            prohibited_count=len(contract.prohibited_operations),
        )
        return cls(contract)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecContractEnforcer:
        """Build an enforcer from an inline dict (useful for testing and harness injection)."""
        contract = SpecContract(
            allowed_action_types=data.get("allowed_action_types", []),
            prohibited_operations=data.get("prohibited_operations", []),
            scope_boundary=data.get("scope_boundary", ""),
        )
        return cls(contract)

    # ── Public API ────────────────────────────────────────────────────────────

    def validate_action(self, action_type: str) -> None:
        """Assert the action is within the spec contract.

        Raises:
            SpecViolationError: if the action is prohibited or not in the allowed list.
        """
        contract = self._contract

        if action_type in contract._prohibited:
            logger.warning(
                "spec_contract.violation.prohibited",
                action_type=action_type,
                prohibited_operations=contract.prohibited_operations,
            )
            raise SpecViolationError(
                f"Action '{action_type}' is explicitly prohibited by the spec contract. "
                f"Prohibited: {contract.prohibited_operations}"
            )

        # If allowed_action_types is empty the contract is permissive (no positive list).
        if contract.allowed_action_types and action_type not in contract._allowed:
            logger.warning(
                "spec_contract.violation.not_in_allowed_list",
                action_type=action_type,
                allowed_action_types=contract.allowed_action_types,
            )
            raise SpecViolationError(
                f"Action '{action_type}' is not in the spec contract's allowed_action_types. "
                f"Allowed: {contract.allowed_action_types}. "
                "This action requires a HITL escalation or spec amendment."
            )

        logger.debug("spec_contract.action_allowed", action_type=action_type)

    def inject_contract(self, system_prompt: str) -> str:
        """Append a [SPEC_CONTRACT] block to the system prompt.

        The block instructs the LLM of its permission boundaries so it cannot
        claim ignorance when proposing out-of-scope actions.
        """
        contract = self._contract
        allowed_str = (
            ", ".join(contract.allowed_action_types) if contract.allowed_action_types else "any"
        )
        prohibited_str = (
            ", ".join(contract.prohibited_operations)
            if contract.prohibited_operations
            else "none declared"
        )
        block = (
            "\n\n[SPEC_CONTRACT]\n"
            f"You are ONLY permitted to: {allowed_str}\n"
            f"You MUST NOT: {prohibited_str}\n"
        )
        if contract.scope_boundary:
            block += f"Scope boundary: {contract.scope_boundary}\n"
        block += "Any action outside this scope MUST trigger a HITL escalation.\n[/SPEC_CONTRACT]"
        return system_prompt + block

    @property
    def contract(self) -> SpecContract:
        return self._contract
