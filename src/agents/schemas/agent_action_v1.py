"""``agent_action_v1`` — the strict envelope the Reason stage requires from the LLM.

The orchestrator asks the LLM to emit a JSON object matching this schema. The
payload is validated *before* the action is routed: a malformed or hallucinated
payload must never silently proceed (ADR-0054). The LLM's self-reported confidence
is advisory only — the system risk scorer owns the final score (ADR-0011/0053).

Validation policy (fail-closed):
  - JSON that does not parse                       → invalid, action_type="unknown"
  - missing action_type (and no legacy "action")  → invalid, action_type="unknown"
  - a present enum field with an out-of-set value  → invalid (errors recorded)
  - a present field with the wrong primitive type  → invalid (errors recorded)
  - missing *optional* fields                      → filled with safe defaults

Backward compatibility: a legacy payload that omits ``schema_version`` and uses the
short ``{"action": ..., "parameters": ...}`` form is accepted (mapped onto the
envelope with defaults) and reported valid, provided an action name is present and
any fields it *does* declare are well-formed.

Spec: specs/ai/agent-design.md, specs/ai/hitl-hotl.md
ADR:  ADR-0054 (structured governance contracts), ADR-0053, ADR-0011
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "agent_action_v1"

VALID_ENVIRONMENTS: frozenset[str] = frozenset({"local", "dev", "staging", "production"})
VALID_OPERATIONS: frozenset[str] = frozenset(
    {"read", "create", "update", "delete", "execute", "deploy", "notify"}
)
VALID_CLASSIFICATIONS: frozenset[str] = frozenset({"none", "L1", "L2", "L3", "L4"})

# Fields that the risk scorer / action policy read out of `parameters`.
_PARAM_MERGE_FIELDS: tuple[str, ...] = (
    "data_classification",
    "external_effect",
    "reversible",
    "target_environment",
    "operation",
    "entity_count",
)


@dataclass
class AgentAction:
    """A parsed, validated agent action envelope.

    ``is_valid`` is False when the payload failed structural validation; callers
    MUST route invalid actions to HITL or reject them — never execute silently.
    """

    action_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    intent: str = ""
    tool_name: str = ""
    target_system: str = ""
    target_environment: str = "local"
    operation: str = "read"
    data_classification: str = "none"
    external_effect: bool = False
    reversible: bool = True
    compensating_action: str | None = None
    agent_confidence: float = 0.0
    requires_human_reason: str = ""

    is_valid: bool = True
    legacy: bool = False
    validation_errors: list[str] = field(default_factory=list)
    # Governance fields the agent explicitly declared (drives merged_parameters()).
    provided_governance_fields: frozenset[str] = field(default_factory=frozenset)

    def merged_parameters(self) -> dict[str, Any]:
        """Return ``parameters`` enriched with the envelope fields the scorer reads.

        Only governance fields the agent *explicitly declared* are merged — envelope
        defaults are not injected, so the returned parameters reflect what the agent
        actually proposed. Envelope values never overwrite an explicit parameter of
        the same key.
        """
        merged = dict(self.parameters)
        envelope = {
            "data_classification": self.data_classification,
            "external_effect": self.external_effect,
            "reversible": self.reversible,
            "target_environment": self.target_environment,
            "operation": self.operation,
        }
        for key, value in envelope.items():
            if key in self.provided_governance_fields:
                merged.setdefault(key, value)
        return merged


def _coerce_bool(value: Any, default: bool, field_name: str, errors: list[str]) -> bool:
    if isinstance(value, bool):
        return value
    errors.append(f"field '{field_name}' must be a boolean, got {type(value).__name__}")
    return default


def _coerce_float(value: Any, default: float, field_name: str, errors: list[str]) -> float:
    if isinstance(value, bool):  # bool is a subclass of int — reject explicitly
        errors.append(f"field '{field_name}' must be a number, got bool")
        return default
    if isinstance(value, (int, float)):
        return float(value)
    errors.append(f"field '{field_name}' must be a number, got {type(value).__name__}")
    return default


def _validate_enum(
    value: Any, allowed: frozenset[str], default: str, field_name: str, errors: list[str]
) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    errors.append(f"field '{field_name}' value {value!r} is not one of {sorted(allowed)}")
    return default


def parse_agent_action(raw: str | dict[str, Any]) -> AgentAction:
    """Parse and validate an LLM action payload into an :class:`AgentAction`.

    Never raises — a malformed payload yields ``AgentAction(is_valid=False)`` so the
    orchestrator can route it to HITL or block it deterministically.
    """
    errors: list[str] = []

    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return AgentAction(
                action_type="unknown",
                is_valid=False,
                validation_errors=["payload is not valid JSON"],
            )
    else:
        data = raw

    if not isinstance(data, dict):
        return AgentAction(
            action_type="unknown",
            is_valid=False,
            validation_errors=["payload is not a JSON object"],
        )

    declared_version = data.get("schema_version")
    legacy = declared_version is None
    if declared_version is not None and declared_version != SCHEMA_VERSION:
        errors.append(
            f"unsupported schema_version {declared_version!r} (expected {SCHEMA_VERSION!r})"
        )

    # action_type (accept legacy "action")
    action_type = data.get("action_type") or data.get("action")
    if not isinstance(action_type, str) or not action_type.strip():
        return AgentAction(
            action_type="unknown",
            is_valid=False,
            legacy=legacy,
            validation_errors=[*errors, "missing or empty action_type"],
        )

    parameters = data.get("parameters", {})
    if not isinstance(parameters, dict):
        errors.append("field 'parameters' must be an object")
        parameters = {}

    # Optional enum / typed fields — validate only when present.
    target_environment = "local"
    if "target_environment" in data:
        target_environment = _validate_enum(
            data["target_environment"],
            VALID_ENVIRONMENTS,
            "local",
            "target_environment",
            errors,
        )

    operation = "read"
    if "operation" in data:
        operation = _validate_enum(data["operation"], VALID_OPERATIONS, "read", "operation", errors)

    data_classification = "none"
    if "data_classification" in data:
        data_classification = _validate_enum(
            data["data_classification"],
            VALID_CLASSIFICATIONS,
            "none",
            "data_classification",
            errors,
        )

    external_effect = (
        _coerce_bool(data["external_effect"], False, "external_effect", errors)
        if "external_effect" in data
        else False
    )
    reversible = (
        _coerce_bool(data["reversible"], True, "reversible", errors)
        if "reversible" in data
        else True
    )
    agent_confidence = (
        _coerce_float(data["agent_confidence"], 0.0, "agent_confidence", errors)
        if "agent_confidence" in data
        else 0.0
    )

    compensating_action = data.get("compensating_action")
    if compensating_action is not None and not isinstance(compensating_action, str):
        errors.append("field 'compensating_action' must be a string or null")
        compensating_action = None

    provided = frozenset(f for f in _PARAM_MERGE_FIELDS if f in data)

    return AgentAction(
        action_type=action_type.strip(),
        parameters=parameters,
        schema_version=SCHEMA_VERSION,
        intent=str(data.get("intent", "")),
        tool_name=str(data.get("tool_name", "")),
        target_system=str(data.get("target_system", "")),
        target_environment=target_environment,
        operation=operation,
        data_classification=data_classification,
        external_effect=external_effect,
        reversible=reversible,
        compensating_action=compensating_action,
        agent_confidence=agent_confidence,
        requires_human_reason=str(data.get("requires_human_reason", "")),
        is_valid=len(errors) == 0,
        legacy=legacy,
        validation_errors=errors,
        provided_governance_fields=provided,
    )
