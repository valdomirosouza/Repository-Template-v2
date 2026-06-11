"""Risk calibration golden dataset — locks expected scoring + routing behaviour.

ADR-0054 / ADR-0011 — the 5-factor RiskScorer weights exist, but without a golden
dataset a weight or keyword change could silently shift routing. This parametrized
calibration matrix pins:

    scenario (action_type + parameters)  →  expected score (±tol)  →  routing tier

If a change to `risk_scorer.py` moves any scenario across a routing boundary, this
test fails — forcing an explicit, reviewed recalibration (and a CHANGELOG/ADR note).

Routing tiers follow the Decision Model in specs/ai/hitl-hotl.md:
    score <  hitl_risk_threshold (0.4)  →  LOW    → HOTL (execute, notify)
    0.4 ≤ score < 0.7                   →  MEDIUM → HITL (block, approve)
    score ≥ 0.7                         →  HIGH   → HITL (block, mandatory approve)
"""

from __future__ import annotations

import pytest

from src.agents.risk_scorer import RiskScorer
from src.shared.config import Settings

_TOL = 0.005

# Calibrate routing against the CANONICAL DEFAULT threshold read straight from the model schema —
# not the global `settings` singleton, which reflects the ambient .env/OS env. The golden matrix
# below is authored against this default (0.4), so the test must be hermetic to a local .env that
# overrides HITL_RISK_THRESHOLD (issue: env-coupled calibration test).
_HITL_THRESHOLD: float = Settings.model_fields["hitl_risk_threshold"].default


def _tier(score: float) -> str:
    if score < 0.4:
        return "LOW"
    if score < 0.7:
        return "MEDIUM"
    return "HIGH"


def _route(score: float) -> str:
    return "HOTL" if score < _HITL_THRESHOLD else "HITL"


# id, action_type, parameters, expected_score, expected_tier, expected_route
CALIBRATION_MATRIX = [
    ("read_simple", "read-db-record", {}, 0.105, "LOW", "HOTL"),
    ("list_simple", "list-users", {}, 0.105, "LOW", "HOTL"),
    ("write_simple", "write-db-record", {}, 0.315, "LOW", "HOTL"),
    ("read_moderate_scale", "read-records", {"entity_count": 50}, 0.165, "LOW", "HOTL"),
    ("read_with_l1_pii", "read-profile", {"ssn": "[SSN]"}, 0.255, "LOW", "HOTL"),
    ("send_email_external", "send-email", {}, 0.515, "MEDIUM", "HITL"),
    ("delete_single", "delete-user-record", {}, 0.42, "MEDIUM", "HITL"),
    ("export_external", "export-report", {}, 0.445, "MEDIUM", "HITL"),
    ("update_bulk", "update-records", {"batch_size": 500}, 0.435, "MEDIUM", "HITL"),
    ("delete_mass", "delete-all-records", {"entity_count": 5000}, 0.60, "MEDIUM", "HITL"),
    ("drop_table_bulk", "drop-table", {"entity_count": 2000}, 0.60, "MEDIUM", "HITL"),
    (
        "delete_export_pii_mass",
        "delete-export-api",
        {"entity_count": 5000, "payload": "[CARD]"},
        0.95,
        "HIGH",
        "HITL",
    ),
]


@pytest.fixture(scope="module")
def scorer() -> RiskScorer:
    # No bias provider → rejection_rate factor is 0.0 (deterministic golden values).
    return RiskScorer()


@pytest.mark.parametrize(
    "scenario_id,action_type,parameters,expected_score,expected_tier,expected_route",
    CALIBRATION_MATRIX,
    ids=[row[0] for row in CALIBRATION_MATRIX],
)
def test_risk_calibration(
    scorer: RiskScorer,
    scenario_id: str,
    action_type: str,
    parameters: dict,
    expected_score: float,
    expected_tier: str,
    expected_route: str,
) -> None:
    score, _components = scorer.score(action_type, parameters)

    assert score == pytest.approx(expected_score, abs=_TOL), (
        f"[{scenario_id}] score {score:.3f} drifted from golden {expected_score:.3f}. "
        "If this change is intentional, update the calibration matrix and note it in "
        "CHANGELOG/ADR."
    )
    assert _tier(score) == expected_tier, (
        f"[{scenario_id}] tier changed: {_tier(score)} != {expected_tier} (score={score:.3f})"
    )
    assert _route(score) == expected_route, (
        f"[{scenario_id}] ROUTING CHANGED: {_route(score)} != {expected_route} "
        f"(score={score:.3f}). This shifts oversight behaviour — requires approval."
    )


def test_calibration_matrix_has_minimum_scenarios() -> None:
    # Acceptance criterion: ≥ 8 scenarios in the matrix.
    assert len(CALIBRATION_MATRIX) >= 8


def test_calibration_covers_all_tiers() -> None:
    tiers = {row[4] for row in CALIBRATION_MATRIX}
    assert {"LOW", "MEDIUM", "HIGH"} <= tiers


def test_calibration_covers_both_routes() -> None:
    routes = {row[5] for row in CALIBRATION_MATRIX}
    assert {"HOTL", "HITL"} <= routes
