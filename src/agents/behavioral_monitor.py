"""Behavioral drift monitor for agent action proposal patterns.

Tracks per-task-type action proposal frequency using an in-memory counter store
(Redis-backed in production). Flags actions whose historical frequency falls below
the anomaly threshold as behavioral drift — possible prompt injection or model drift.

On anomaly detection:
  - Sets OTel span attribute `behavioral.drift_detected=true`
  - Increments Prometheus counter `agent_behavioral_anomaly_total`
  - Returns True so the caller can escalate to HITL

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 3 (BM1, BM3)
ADR:  ADR-0049
Issue: #34
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from opentelemetry import trace as otel_trace

from src.observability.logger import get_logger
from src.observability.metrics import AGENT_BEHAVIORAL_ANOMALY_COUNTER

logger = get_logger("behavioral_monitor")

# Minimum observation count before anomaly detection activates.
# Below this count the baseline is not yet reliable.
_MIN_OBSERVATIONS = 20

# A proposed action is considered anomalous if its historical frequency for this
# task_type is below this fraction of all observed actions for that task_type.
_ANOMALY_FREQUENCY_THRESHOLD = 0.01  # 1%


@dataclass
class ActionFrequency:
    """Per-task-type action proposal frequency counters."""

    counts: dict[str, int] = field(default_factory=dict)
    total: int = 0

    def record(self, action_type: str) -> None:
        self.counts[action_type] = self.counts.get(action_type, 0) + 1
        self.total += 1

    def frequency(self, action_type: str) -> float:
        """Return the fraction of proposals that were this action_type (0.0-1.0)."""
        if self.total == 0:
            return 0.0
        return self.counts.get(action_type, 0) / self.total

    def has_baseline(self) -> bool:
        return self.total >= _MIN_OBSERVATIONS


class BehavioralMonitor:
    """Tracks agent action proposal patterns and detects behavioral drift.

    Usage::

        monitor = BehavioralMonitor()
        monitor.record_proposal(task_type="summarise", proposed_action="read_file")
        is_drift = monitor.is_anomalous(task_type="summarise", proposed_action="execute_code")
        if is_drift:
            # escalate to HITL
    """

    def __init__(self) -> None:
        self._history: dict[str, ActionFrequency] = defaultdict(ActionFrequency)

    def record_proposal(self, task_type: str, proposed_action: str) -> None:
        """Record a proposed action for the given task_type to build the baseline."""
        self._history[task_type].record(proposed_action)
        logger.debug(
            "behavioral_monitor.recorded",
            task_type=task_type,
            proposed_action=proposed_action,
            total=self._history[task_type].total,
        )

    def is_anomalous(
        self,
        task_type: str,
        proposed_action: str,
        allowed_action_types: list[str] | None = None,
    ) -> bool:
        """Return True if the proposed action looks anomalous for this task_type.

        Anomaly criteria:
          1. A baseline of at least _MIN_OBSERVATIONS has been collected, AND
          2. The proposed action has a historical frequency < _ANOMALY_FREQUENCY_THRESHOLD
             for this task_type, AND
          3. (Optional) The proposed action is not in the spec's allowed_action_types.

        On anomaly: emits OTel span attribute and increments Prometheus counter.
        """
        freq_record = self._history[task_type]
        if not freq_record.has_baseline():
            return False

        freq = freq_record.frequency(proposed_action)
        # If an allowed list is provided and the action is on it, it is never anomalous
        # regardless of historical frequency (spec amendment or new capability).
        # If no allowed list is provided, frequency alone determines anomaly status.
        in_allowed_list = (
            proposed_action in allowed_action_types if allowed_action_types is not None else False
        )

        is_drift = freq < _ANOMALY_FREQUENCY_THRESHOLD and not in_allowed_list
        if is_drift:
            logger.warning(
                "behavioral_monitor.drift_detected",
                task_type=task_type,
                proposed_action=proposed_action,
                historical_frequency=freq,
                baseline_total=freq_record.total,
            )
            # OTel: mark active span
            span = otel_trace.get_current_span()
            if span.is_recording():
                span.set_attribute("behavioral.drift_detected", True)
                span.set_attribute("behavioral.anomalous_action", proposed_action)
                span.set_attribute("behavioral.historical_frequency", freq)

            # Prometheus
            AGENT_BEHAVIORAL_ANOMALY_COUNTER.labels(
                task_type=task_type,
                action_type=proposed_action,
            ).inc()

        return is_drift

    def frequency(self, task_type: str, action_type: str) -> float:
        """Expose historical frequency for testing and dashboards."""
        return self._history[task_type].frequency(action_type)

    def observation_count(self, task_type: str) -> int:
        """Return total observations recorded for task_type."""
        return self._history[task_type].total

    def reset(self, task_type: str | None = None) -> None:
        """Clear history. Accepts an optional task_type to clear only that entry."""
        if task_type is None:
            self._history.clear()
        else:
            self._history.pop(task_type, None)


# Module-level singleton — can be replaced in tests via dependency injection.
default_behavioral_monitor = BehavioralMonitor()
