"""Risk scorer — 5-factor weighted evaluation of agent action risk.

Computes an objective risk_score [0.0, 1.0] from observable action properties,
replacing the LLM-self-reported score with a deterministic, auditable assessment.

Spec: specs/ai/hitl-hotl.md (Risk Scoring Inputs)
ADR:  ADR-0011 (HITL/HOTL Model)

Factor weights (sum = 1.0):
    irreversibility   0.35  — delete/write > read
    external_effect   0.25  — external system > internal
    scale             0.20  — bulk operations score higher
    data_sensitivity  0.15  — L1/L2 PII tokens in masked payload score higher
    rejection_rate    0.05  — learning signal from prior HITL decisions (FeedbackLoop)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# ── Weights (must sum to 1.0) ─────────────────────────────────────────────────

_W_IRREVERSIBILITY = 0.35
_W_EXTERNAL = 0.25
_W_SCALE = 0.20
_W_SENSITIVITY = 0.15
_W_REJECTION = 0.05

# ── Action classification ─────────────────────────────────────────────────────

_IRREVERSIBLE_KEYWORDS = frozenset(
    ("delete", "drop", "destroy", "truncate", "purge", "wipe", "revoke", "terminate")
)
_HIGH_WRITE_KEYWORDS = frozenset(
    (
        "write",
        "update",
        "create",
        "insert",
        "modify",
        "rotate",
        "send",
        "push",
        "publish",
        "deploy",
        "execute",
        "run",
        "apply",
    )
)
_READ_KEYWORDS = frozenset(("read", "get", "list", "query", "search", "fetch", "view", "describe"))

_EXTERNAL_KEYWORDS = frozenset(
    ("external", "api", "webhook", "email", "sms", "notification", "payment", "export")
)

# Masked PII tokens produced by pii_filter.py — presence in parameters signals PII in scope
_L1_TOKENS = frozenset(("[CPF]", "[SSN]", "[CARD]", "[HEALTH]"))
_L2_TOKENS = frozenset(("[EMAIL]", "[PHONE]", "[IP]", "[NAME]", "[ADDRESS]"))
_L3_TOKENS = frozenset(("[TOKEN]", "[UUID]", "[SESSION]", "[USER_ID]"))


# ── Bias provider protocol (satisfied by FeedbackLoop) ────────────────────────


class BiasProvider(Protocol):
    def get_bias(self, action_type: str) -> float: ...


# ── Score components ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RiskComponents:
    """Individual factor scores before weighting — useful for audit logging."""

    irreversibility: float
    external_effect: float
    scale: float
    data_sensitivity: float
    rejection_rate: float

    @property
    def weighted_total(self) -> float:
        raw = (
            _W_IRREVERSIBILITY * self.irreversibility
            + _W_EXTERNAL * self.external_effect
            + _W_SCALE * self.scale
            + _W_SENSITIVITY * self.data_sensitivity
            + _W_REJECTION * self.rejection_rate
        )
        return min(1.0, max(0.0, raw))


# ── Public scorer ─────────────────────────────────────────────────────────────


class RiskScorer:
    """Deterministic 5-factor risk scorer.

    Inject an optional ``bias_provider`` (FeedbackLoop) to incorporate the
    historical rejection-rate learning signal.

    Usage::

        scorer = RiskScorer(bias_provider=feedback_loop)
        score, components = scorer.score("delete_user_records", params)
        # score ∈ [0.0, 1.0]; route to HITL if score >= settings.hitl_risk_threshold
    """

    def __init__(self, bias_provider: BiasProvider | None = None) -> None:
        self._bias = bias_provider

    def score(
        self,
        action_type: str,
        parameters: dict[str, Any],
    ) -> tuple[float, RiskComponents]:
        """Return (risk_score, components) for the given action.

        The returned score replaces any LLM-self-reported risk value.
        """
        rejection_rate = self._bias.get_bias(action_type) if self._bias is not None else 0.0

        components = RiskComponents(
            irreversibility=_score_irreversibility(action_type),
            external_effect=_score_external(action_type, parameters),
            scale=_score_scale(parameters),
            data_sensitivity=_score_sensitivity(parameters),
            rejection_rate=min(1.0, max(0.0, rejection_rate)),
        )
        return components.weighted_total, components


# ── Factor scoring functions ──────────────────────────────────────────────────


def _score_irreversibility(action_type: str) -> float:
    lower = action_type.lower()
    if any(k in lower for k in _IRREVERSIBLE_KEYWORDS):
        return 1.0
    if any(k in lower for k in _HIGH_WRITE_KEYWORDS):
        return 0.7
    if any(k in lower for k in _READ_KEYWORDS):
        return 0.1
    return 0.5  # unknown — default to medium


def _score_external(action_type: str, parameters: dict[str, Any]) -> float:
    lower = action_type.lower()
    if any(k in lower for k in _EXTERNAL_KEYWORDS):
        return 1.0
    if parameters.get("external") is True:
        return 1.0
    if str(parameters.get("target_env", "")).lower() in ("production", "prod"):
        return 0.8
    return 0.2


def _score_scale(parameters: dict[str, Any]) -> float:
    for key in ("count", "entity_count", "limit", "batch_size", "size"):
        val = parameters.get(key)
        if isinstance(val, (int, float)) and val > 0:
            if val >= 1000:
                return 1.0
            if val >= 100:
                return 0.7
            if val >= 10:
                return 0.4
            return 0.1
    # Implicit bulk indicators
    if parameters.get("bulk") or parameters.get("all") or parameters.get("batch"):
        return 0.8
    return 0.1


def _score_sensitivity(parameters: dict[str, Any]) -> float:
    payload_str = str(parameters)
    if any(token in payload_str for token in _L1_TOKENS):
        return 1.0
    if any(token in payload_str for token in _L2_TOKENS):
        return 0.6
    if any(token in payload_str for token in _L3_TOKENS):
        return 0.3
    return 0.0
