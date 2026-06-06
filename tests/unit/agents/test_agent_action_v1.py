"""Unit tests for the agent_action_v1 envelope parser/validator.

ADR-0054 — structured governance contract for agent output.
Invalid output must be flagged (is_valid=False) so the orchestrator can route it
to HITL or block it; it must never silently proceed.
"""

from __future__ import annotations

import json

import pytest

from src.agents.schemas import (
    SCHEMA_VERSION,
    AgentAction,
    parse_agent_action,
)

# ── Valid v1 envelopes ────────────────────────────────────────────────────────


def _full_v1() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "intent": "fetch a record for display",
        "action_type": "read-db-record",
        "tool_name": "read-db-record",
        "target_system": "postgres",
        "target_environment": "staging",
        "operation": "read",
        "parameters": {"record_id": "synthetic-123"},
        "data_classification": "L3",
        "external_effect": False,
        "reversible": True,
        "compensating_action": None,
        "agent_confidence": 0.8,
        "requires_human_reason": "",
    }


def test_full_valid_envelope_parses_and_is_valid():
    action = parse_agent_action(_full_v1())
    assert action.is_valid is True
    assert action.validation_errors == []
    assert action.action_type == "read-db-record"
    assert action.operation == "read"
    assert action.data_classification == "L3"
    assert action.legacy is False


def test_valid_envelope_accepts_json_string():
    action = parse_agent_action(json.dumps(_full_v1()))
    assert action.is_valid is True
    assert action.action_type == "read-db-record"


def test_merged_parameters_include_envelope_fields():
    action = parse_agent_action(_full_v1())
    merged = action.merged_parameters()
    assert merged["record_id"] == "synthetic-123"
    assert merged["data_classification"] == "L3"
    assert merged["operation"] == "read"
    assert merged["external_effect"] is False


def test_explicit_parameter_not_overwritten_by_envelope():
    payload = _full_v1()
    payload["parameters"] = {"data_classification": "L1"}  # explicit param wins
    action = parse_agent_action(payload)
    assert action.merged_parameters()["data_classification"] == "L1"


# ── Legacy backward compatibility ─────────────────────────────────────────────


def test_legacy_short_form_is_valid():
    action = parse_agent_action({"action": "read-db-record", "parameters": {}, "risk_score": 0.1})
    assert action.is_valid is True
    assert action.legacy is True
    assert action.action_type == "read-db-record"


def test_legacy_risk_score_is_ignored():
    # LLM-self-reported risk is advisory only — not surfaced on the envelope.
    action = parse_agent_action({"action": "read-db-record", "risk_score": 0.99})
    assert not hasattr(action, "risk_score")


# ── Invalid payloads (fail-closed) ────────────────────────────────────────────


def test_unparseable_json_is_invalid_and_unknown():
    action = parse_agent_action("not valid json {{{{")
    assert action.is_valid is False
    assert action.action_type == "unknown"


def test_non_object_json_is_invalid():
    action = parse_agent_action("[1, 2, 3]")
    assert action.is_valid is False
    assert action.action_type == "unknown"


def test_missing_action_type_is_invalid():
    action = parse_agent_action({"schema_version": SCHEMA_VERSION, "parameters": {}})
    assert action.is_valid is False
    assert action.action_type == "unknown"


def test_empty_action_type_is_invalid():
    action = parse_agent_action({"action_type": "   ", "parameters": {}})
    assert action.is_valid is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_environment", "prod-xyz"),
        ("operation", "obliterate"),
        ("data_classification", "L9"),
    ],
)
def test_bad_enum_value_is_invalid(field, value):
    payload = _full_v1()
    payload[field] = value
    action = parse_agent_action(payload)
    assert action.is_valid is False
    assert any(field in err for err in action.validation_errors)


@pytest.mark.parametrize("field", ["external_effect", "reversible"])
def test_non_boolean_flag_is_invalid(field):
    payload = _full_v1()
    payload[field] = "yes"
    action = parse_agent_action(payload)
    assert action.is_valid is False


def test_string_confidence_is_invalid():
    payload = _full_v1()
    payload["agent_confidence"] = "high"
    action = parse_agent_action(payload)
    assert action.is_valid is False


def test_unsupported_schema_version_is_invalid():
    payload = _full_v1()
    payload["schema_version"] = "agent_action_v2"
    action = parse_agent_action(payload)
    assert action.is_valid is False


def test_non_object_parameters_recorded_as_error():
    payload = _full_v1()
    payload["parameters"] = ["not", "an", "object"]
    action = parse_agent_action(payload)
    assert action.is_valid is False
    assert action.parameters == {}


# ── Type contract ─────────────────────────────────────────────────────────────


def test_returns_agent_action_instance():
    assert isinstance(parse_agent_action(_full_v1()), AgentAction)
