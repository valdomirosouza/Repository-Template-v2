"""Validate the machine-readable governance contracts.

ADR-0054 — phase-gates.yaml and state-template.yaml must be structurally valid and
mutually consistent so agents can enforce gates without parsing Markdown.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_PHASE_GATES = _ROOT / "docs" / "process" / "gates" / "phase-gates.yaml"
_STATE_TEMPLATE = _ROOT / "docs" / "product" / "state-template.yaml"


@pytest.fixture(scope="module")
def gates() -> dict:
    return yaml.safe_load(_PHASE_GATES.read_text())


@pytest.fixture(scope="module")
def state_template() -> dict:
    return yaml.safe_load(_STATE_TEMPLATE.read_text())


# ── phase-gates.yaml ──────────────────────────────────────────────────────────


def test_phase_gates_file_exists():
    assert _PHASE_GATES.exists()


def test_schema_version(gates):
    assert gates["schema_version"] == "phase_gates_v1"


def test_covers_all_fifteen_phases(gates):
    ids = sorted(p["id"] for p in gates["phases"])
    assert ids == list(range(0, 15)), "phase-gates.yaml must define phases 0-14 (ADR-0058)"


def test_phase_zero_is_intake(gates):
    p0 = next(p for p in gates["phases"] if p["id"] == 0)
    assert "Intake" in p0["name"]


def test_ai_safety_phase_present_and_conditional(gates):
    ai = next((p for p in gates["phases"] if p["name"] == "AI Safety & Agent Governance"), None)
    assert ai is not None, "AI Safety & Agent Governance phase must exist (ADR-0058)"
    assert ai["id"] == 10
    assert ai.get("conditional") == "ai_or_agent_change"


def test_each_phase_has_required_fields(gates):
    required = {
        "id",
        "name",
        "primary_actor",
        "required_artifacts",
        "required_approvals",
        "ci_checks",
        "blocking",
        "allowed_agent_actions",
        "prohibited_agent_actions",
        "exit_criteria",
    }
    for phase in gates["phases"]:
        missing = required - set(phase)
        assert not missing, f"phase {phase.get('id')} missing fields: {missing}"


def test_actions_use_known_vocabulary(gates):
    vocab = set(gates["action_vocabulary"])
    for phase in gates["phases"]:
        for action in phase["allowed_agent_actions"] + phase["prohibited_agent_actions"]:
            assert action in vocab, f"phase {phase['id']}: '{action}' not in action_vocabulary"


def test_allowed_and_prohibited_are_disjoint(gates):
    for phase in gates["phases"]:
        overlap = set(phase["allowed_agent_actions"]) & set(phase["prohibited_agent_actions"])
        assert not overlap, f"phase {phase['id']}: actions both allowed and prohibited: {overlap}"


def test_required_approval_roles_are_declared(gates):
    declared = set(gates["roles"])
    for phase in gates["phases"]:
        for role in phase["required_approvals"]:
            assert role in declared, f"phase {phase['id']}: undeclared role '{role}'"


def test_deploy_and_rollback_prohibited_in_development(gates):
    dev = next(p for p in gates["phases"] if p["name"] == "Development")
    assert "deploy" in dev["prohibited_agent_actions"]
    assert "rollback" in dev["prohibited_agent_actions"]


def test_production_phase_requires_cab(gates):
    prod = next(p for p in gates["phases"] if p["name"] == "Production Deployment")
    assert prod.get("requires_cab_approval") is True


# ── state-template.yaml ───────────────────────────────────────────────────────


def test_state_template_exists():
    assert _STATE_TEMPLATE.exists()


def test_state_template_schema(state_template):
    assert state_template["schema_version"] == "feature_state_v1"


def test_state_template_has_governance_fields(state_template):
    for key in (
        "current_phase",
        "approvals",
        "gates_passed",
        "next_allowed_agent_actions",
        "prohibited_agent_actions",
    ):
        assert key in state_template, f"state-template.yaml missing '{key}'"


def test_state_template_current_phase_matches_a_gate(gates, state_template):
    phase_ids = {p["id"] for p in gates["phases"]}
    assert state_template["current_phase"] in phase_ids


def test_state_template_actions_consistent_with_phase_gate(gates, state_template):
    """The template's convenience projection must match phase-gates for its phase."""
    phase = next(p for p in gates["phases"] if p["id"] == state_template["current_phase"])
    assert state_template["next_allowed_agent_actions"] == phase["allowed_agent_actions"]
    assert state_template["prohibited_agent_actions"] == phase["prohibited_agent_actions"]
