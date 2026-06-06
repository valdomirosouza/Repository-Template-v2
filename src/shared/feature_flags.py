"""Feature flag client — thin wrapper around the OpenFeature SDK.

Provides two public APIs:
  - is_autonomous_mode_enabled()  — legacy boolean; preserved for backward compat
  - get_autonomy_level(action_type, risk_score) — graduated autonomy (SPEC-autonomous-mode-levels)

Falls back to settings defaults when the SDK is unavailable (local dev without flagd,
or SDK not yet configured).

Spec: SPEC-autonomous-mode-levels, specs/system/architecture.md
ADR:  ADR-0015 (Feature Flag Strategy — revised)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from src.shared.config import settings


class AutonomyPrerequisiteError(RuntimeError):
    """Raised when autonomy-tier-ready is enabled but prerequisites are unmet.

    Spec: specs/ai/context-graph.md §5 | ADR: ADR-0041
    Prerequisites:
      1. learning-mode flag is 'active'
      2. src/agents/context_graph.py is present (context graph implemented)
      3. governance-council-approved label was applied to the enabling PR
    """


class AutonomyLevel(StrEnum):
    """Graduated autonomy levels from most to least permissive.

    Evaluation order in get_autonomy_level(): FULL → MEDIUM_RISK → LOW_RISK
    → TESTS_ONLY → READ_ONLY → NONE.
    """

    FULL = "full"  # any action, any risk — governance approval required
    MEDIUM_RISK = "medium-risk"  # risk_score ≤ autonomy_medium_risk_threshold — HOTL
    LOW_RISK = "low-risk"  # risk_score < autonomy_low_risk_threshold — no HITL
    TESTS_ONLY = "tests-only"  # test-generation/execution actions only
    READ_ONLY = "read-only"  # read-only actions only
    NONE = "none"  # all actions require HITL (safest default)


# ── Flag name constants ───────────────────────────────────────────────────────

_FLAG_FULL = "autonomous-mode-full"
_FLAG_MEDIUM_RISK = "autonomous-mode-medium-risk"
_FLAG_LOW_RISK = "autonomous-mode-low-risk"
_FLAG_TESTS_ONLY = "autonomous-mode-tests-only"
_FLAG_READ_ONLY = "autonomous-mode-read-only"
_FLAG_LEGACY = "autonomous-mode"


# ── Public API ────────────────────────────────────────────────────────────────


def is_autonomous_mode_enabled() -> bool:
    """Return True if the 'autonomous-mode' feature flag is enabled.

    Preserved for backward compatibility. New callers should use
    get_autonomy_level() for finer-grained control.

    Evaluation order:
    1. OpenFeature SDK (flagd in production, InMemoryProvider in tests).
    2. settings.autonomous_mode_enabled fallback.
    """
    try:
        from openfeature import api

        client = api.get_client()
        return client.get_boolean_value(_FLAG_LEGACY, settings.autonomous_mode_enabled)
    except Exception:
        return settings.autonomous_mode_enabled


def get_autonomy_level(action_type: str, risk_score: float) -> AutonomyLevel:
    """Return the highest autonomy level applicable for this action.

    Evaluates all five granular flags in order from most to least permissive.
    Returns the first matching enabled level, or AutonomyLevel.NONE if all
    flags are disabled (safest default).

    Args:
        action_type: e.g. "read_file", "generate_test", "deploy" — used to
                     constrain READ_ONLY and TESTS_ONLY levels.
        risk_score:  0.0-1.0 from the agent or orchestrator — used to constrain
                     LOW_RISK and MEDIUM_RISK levels.

    Returns:
        AutonomyLevel — never raises; falls back to NONE on SDK errors.
    """
    try:
        from openfeature import api

        client = api.get_client()
        return _evaluate(client, action_type, risk_score)
    except Exception:
        return AutonomyLevel.NONE


# ── Internal evaluation ───────────────────────────────────────────────────────


def _evaluate(client: Any, action_type: str, risk_score: float) -> AutonomyLevel:
    """Evaluate flags in priority order and return the first applicable level."""
    read_only_types = _parse_action_types(settings.autonomy_read_only_action_types)
    test_types = _parse_action_types(settings.autonomy_test_action_types)

    # FULL — any action, any risk (governance approval required before enabling)
    if _flag_enabled(client, _FLAG_FULL):
        return AutonomyLevel.FULL

    # MEDIUM_RISK — risk_score ≤ medium threshold → HOTL (monitor, no block)
    if _flag_enabled(client, _FLAG_MEDIUM_RISK):
        if risk_score <= settings.autonomy_medium_risk_threshold:
            return AutonomyLevel.MEDIUM_RISK

    # LOW_RISK — risk_score strictly below low threshold → no HITL
    if _flag_enabled(client, _FLAG_LOW_RISK):
        if risk_score < settings.autonomy_low_risk_threshold:
            return AutonomyLevel.LOW_RISK

    # TESTS_ONLY — action_type must be a test action
    if _flag_enabled(client, _FLAG_TESTS_ONLY):
        if action_type in test_types:
            return AutonomyLevel.TESTS_ONLY

    # READ_ONLY — action_type must be a read-only action
    if _flag_enabled(client, _FLAG_READ_ONLY):
        if action_type in read_only_types:
            return AutonomyLevel.READ_ONLY

    return AutonomyLevel.NONE


def _flag_enabled(client: Any, flag_name: str) -> bool:
    """Evaluate a boolean flag; returns False on any error."""
    try:
        return bool(client.get_boolean_value(flag_name, False))
    except Exception:
        return False


def _parse_action_types(csv: str) -> frozenset[str]:
    """Parse a comma-separated action type list from settings into a frozenset."""
    return frozenset(part.strip() for part in csv.split(",") if part.strip())


def is_autonomy_tier_ready() -> bool:
    """Return True if the autonomy-tier-ready flag is enabled.

    Raises AutonomyPrerequisiteError if the flag is enabled but prerequisites
    are not met (learning-mode not active, or context_graph.py absent).

    Spec: specs/ai/context-graph.md §5 | ADR: ADR-0041
    """
    try:
        from openfeature import api

        client = api.get_client()
        enabled = client.get_boolean_value("autonomy-tier-ready", False)
    except Exception:
        return False

    if not enabled:
        return False

    # Guard: check prerequisites before allowing FULL autonomy.
    missing: list[str] = []

    if get_learning_mode() != "active":
        missing.append("learning-mode flag must be set to 'active' (currently passive)")

    from pathlib import Path

    if not (Path(__file__).parent.parent / "agents" / "context_graph.py").exists():
        missing.append("src/agents/context_graph.py not found — implement context graph first")

    if missing:
        raise AutonomyPrerequisiteError(
            "autonomy-tier-ready flag is enabled but prerequisites are unmet:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    return True


def get_learning_mode() -> str:
    """Return the current learning-mode flag value: 'passive' (default) or 'active'.

    Spec: specs/ai/learn-stage.md §3 | ADR: ADR-0038
    - passive: precedents stored, surfaced in logs/Grafana only (safe default)
    - active:  precedents injected into Reason-stage LLM prompt (requires governance sign-off)
    """
    try:
        from openfeature import api

        client = api.get_client()
        return str(client.get_string_value("learning-mode", "passive"))
    except Exception:
        return "passive"
