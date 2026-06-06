"""Learn stage — Perceive → Reason → Act → Learn feedback loop.

Spec:  specs/ai/learn-stage.md
ADR:   ADR-0038
Issue: #15
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from src.observability.logger import get_logger
from src.observability.metrics import AGENT_LEARN_PRECEDENTS_INJECTED

logger = get_logger(__name__)

_FEEDBACK_WINDOW_DAYS = 30
_PRECEDENT_TAG = "learn:outcome"


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class OutcomeFeedback:
    action_type: str
    payload_hash: str
    decision: str  # "approved" | "rejected"
    decision_reason: str
    agent_id: str
    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    outcome_signal: str = "unknown"  # "success" | "failure" | "unknown"
    recorded_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class Precedent:
    action_type: str
    decision: str
    reason: str
    occurrences: int = 1


@dataclass
class BiasReport:
    rejection_rate: float
    approval_rate: float
    total_decisions: int
    top_rejected_action_types: list[str]
    window_days: int = _FEEDBACK_WINDOW_DAYS


# ── FeedbackLearner ───────────────────────────────────────────────────────────


class FeedbackLearner:
    """Stores HITL decision outcomes and surfaces precedents at the Reason stage.

    Storage is an in-process list (suitable for testing and local dev).
    Production deployments should swap _store for a Redis-backed or
    PostgresVectorStore-backed implementation.
    """

    def __init__(self) -> None:
        # List of (OutcomeFeedback, recorded_at_datetime) tuples
        self._store: list[tuple[OutcomeFeedback, datetime]] = []

    # ── Write path (called after HITLGateway.record_decision) ────────────────

    def record(self, feedback: OutcomeFeedback) -> None:
        """Store a HITL decision outcome for future precedent retrieval."""
        now = datetime.now(UTC)
        self._store.append((feedback, now))
        logger.info(
            "learn.outcome.recorded",
            action_type=feedback.action_type,
            decision=feedback.decision,
            feedback_id=feedback.feedback_id,
        )

    # ── Read path (called at Reason stage) ───────────────────────────────────

    def get_similar_precedents(
        self,
        action_type: str,
        payload_hash: str,
        n: int = 5,
    ) -> list[Precedent]:
        """Return up to *n* precedents matching *action_type* within the feedback window."""
        cutoff = datetime.now(UTC) - timedelta(days=_FEEDBACK_WINDOW_DAYS)
        matches: list[OutcomeFeedback] = [
            fb for fb, ts in self._store if ts >= cutoff and fb.action_type == action_type
        ]
        # Prefer exact payload-hash matches first, then any matching action_type.
        exact = [m for m in matches if m.payload_hash == payload_hash]
        rest = [m for m in matches if m.payload_hash != payload_hash]
        ordered = (exact + rest)[:n]

        precedents: dict[tuple[str, str], Precedent] = {}
        for fb in ordered:
            key = (fb.action_type, fb.decision)
            if key in precedents:
                precedents[key].occurrences += 1
            else:
                precedents[key] = Precedent(
                    action_type=fb.action_type,
                    decision=fb.decision,
                    reason=fb.decision_reason,
                )
        return list(precedents.values())

    def build_precedents_block(
        self,
        action_type: str,
        payload_hash: str,
        mode: str,
    ) -> str | None:
        """Return a [PRECEDENTS] prompt block if mode is 'active', else None."""
        if mode != "active":
            return None
        precedents = self.get_similar_precedents(action_type, payload_hash)
        if not precedents:
            return None

        lines: list[str] = []
        for p in precedents:
            lines.append(
                f"- action: {p.action_type}, prior_outcome: {p.decision} "
                f"({p.occurrences}x), reason: {p.reason}"
            )
            AGENT_LEARN_PRECEDENTS_INJECTED.labels(
                action_type=action_type, outcome_influenced="true"
            ).inc()

        return "[PRECEDENTS]\n" + "\n".join(lines) + "\n[/PRECEDENTS]"

    # ── Bias summary (feeds make agent-feedback-check) ────────────────────────

    def get_bias_summary(self) -> BiasReport:
        """Return rejection/approval rates and top rejected action types."""
        cutoff = datetime.now(UTC) - timedelta(days=_FEEDBACK_WINDOW_DAYS)
        recent = [fb for fb, ts in self._store if ts >= cutoff]

        if not recent:
            return BiasReport(
                rejection_rate=0.0,
                approval_rate=1.0,
                total_decisions=0,
                top_rejected_action_types=[],
            )

        total = len(recent)
        rejections = [fb for fb in recent if fb.decision == "rejected"]
        rejection_rate = len(rejections) / total

        rejected_counts: dict[str, int] = {}
        for fb in rejections:
            rejected_counts[fb.action_type] = rejected_counts.get(fb.action_type, 0) + 1
        top_rejected = sorted(rejected_counts, key=rejected_counts.__getitem__, reverse=True)[:5]

        return BiasReport(
            rejection_rate=rejection_rate,
            approval_rate=1.0 - rejection_rate,
            total_decisions=total,
            top_rejected_action_types=top_rejected,
        )

    # ── Convenience factory ───────────────────────────────────────────────────

    @staticmethod
    def feedback_from_hitl_decision(
        action_type: str,
        action_parameters: dict[str, Any],
        decision: str,
        rationale: str,
        agent_id: str,
        request_id: str = "",
    ) -> OutcomeFeedback:
        payload_hash = hashlib.sha256(
            json.dumps(action_parameters, sort_keys=True).encode()
        ).hexdigest()
        return OutcomeFeedback(
            action_type=action_type,
            payload_hash=payload_hash,
            decision=decision,
            decision_reason=rationale,
            agent_id=agent_id,
            action_id=request_id,
        )


# Module-level singleton — replaced in tests via dependency injection.
default_feedback_learner = FeedbackLearner()
