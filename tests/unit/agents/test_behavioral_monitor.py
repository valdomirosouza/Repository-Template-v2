"""Unit tests for BehavioralMonitor — semantic drift detection.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 3 (BM1, BM3)
ADR:  ADR-0049
Issue: #34
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.behavioral_monitor import (
    _MIN_OBSERVATIONS,
    ActionFrequency,
    BehavioralMonitor,
)


class TestActionFrequency:
    def test_initial_total_is_zero(self) -> None:
        af = ActionFrequency()
        assert af.total == 0

    def test_record_increments_total(self) -> None:
        af = ActionFrequency()
        af.record("read_file")
        af.record("read_file")
        assert af.total == 2

    def test_frequency_for_known_action(self) -> None:
        af = ActionFrequency()
        for _ in range(8):
            af.record("read_file")
        for _ in range(2):
            af.record("write_file")
        assert af.frequency("read_file") == pytest.approx(0.8)
        assert af.frequency("write_file") == pytest.approx(0.2)

    def test_frequency_for_unknown_action_is_zero(self) -> None:
        af = ActionFrequency()
        af.record("read_file")
        assert af.frequency("execute_code") == 0.0

    def test_frequency_with_no_observations_is_zero(self) -> None:
        af = ActionFrequency()
        assert af.frequency("any_action") == 0.0

    def test_has_baseline_false_below_min(self) -> None:
        af = ActionFrequency()
        for _ in range(_MIN_OBSERVATIONS - 1):
            af.record("read_file")
        assert not af.has_baseline()

    def test_has_baseline_true_at_min(self) -> None:
        af = ActionFrequency()
        for _ in range(_MIN_OBSERVATIONS):
            af.record("read_file")
        assert af.has_baseline()


class TestBehavioralMonitorRecordAndFrequency:
    def test_record_proposal_tracked(self) -> None:
        monitor = BehavioralMonitor()
        monitor.record_proposal("summarise", "read_file")
        assert monitor.observation_count("summarise") == 1

    def test_multiple_records_accumulate(self) -> None:
        monitor = BehavioralMonitor()
        for _ in range(5):
            monitor.record_proposal("summarise", "read_file")
        assert monitor.observation_count("summarise") == 5

    def test_frequency_reflects_records(self) -> None:
        monitor = BehavioralMonitor()
        for _ in range(9):
            monitor.record_proposal("analyse", "read_file")
        monitor.record_proposal("analyse", "search_code")
        assert monitor.frequency("analyse", "read_file") == pytest.approx(0.9)

    def test_reset_clears_specific_task_type(self) -> None:
        monitor = BehavioralMonitor()
        monitor.record_proposal("summarise", "read_file")
        monitor.record_proposal("analyse", "search_code")
        monitor.reset("summarise")
        assert monitor.observation_count("summarise") == 0
        assert monitor.observation_count("analyse") == 1

    def test_reset_all_clears_everything(self) -> None:
        monitor = BehavioralMonitor()
        monitor.record_proposal("summarise", "read_file")
        monitor.record_proposal("analyse", "search_code")
        monitor.reset()
        assert monitor.observation_count("summarise") == 0
        assert monitor.observation_count("analyse") == 0


class TestBehavioralMonitorIsAnomalous:
    def _build_baseline(self, monitor: BehavioralMonitor, task_type: str, action: str) -> None:
        """Populate enough observations to activate anomaly detection."""
        for _ in range(_MIN_OBSERVATIONS):
            monitor.record_proposal(task_type, action)

    def test_no_baseline_returns_false(self) -> None:
        monitor = BehavioralMonitor()
        monitor.record_proposal("summarise", "read_file")  # only 1 observation
        assert not monitor.is_anomalous("summarise", "execute_code")

    def test_common_action_not_anomalous(self) -> None:
        monitor = BehavioralMonitor()
        self._build_baseline(monitor, "summarise", "read_file")
        assert not monitor.is_anomalous("summarise", "read_file")

    def test_novel_action_flagged_as_anomalous(self) -> None:
        monitor = BehavioralMonitor()
        self._build_baseline(monitor, "summarise", "read_file")
        # "execute_code" has 0% frequency for "summarise"
        assert monitor.is_anomalous("summarise", "execute_code")

    def test_allowed_action_types_prevents_anomaly(self) -> None:
        monitor = BehavioralMonitor()
        self._build_baseline(monitor, "summarise", "read_file")
        # execute_code is new (0%) but is in the allowed list
        assert not monitor.is_anomalous(
            "summarise", "execute_code", allowed_action_types=["read_file", "execute_code"]
        )

    def test_anomaly_increments_prometheus_counter(self) -> None:
        monitor = BehavioralMonitor()
        self._build_baseline(monitor, "summarise", "read_file")
        with patch("src.agents.behavioral_monitor.AGENT_BEHAVIORAL_ANOMALY_COUNTER") as mock_ctr:
            mock_labels = mock_ctr.labels.return_value
            monitor.is_anomalous("summarise", "execute_code")
            mock_ctr.labels.assert_called_once_with(
                task_type="summarise", action_type="execute_code"
            )
            mock_labels.inc.assert_called_once()

    def test_rare_action_below_threshold_is_anomalous(self) -> None:
        monitor = BehavioralMonitor()
        # 100 observations: 99 read_file, 1 search_code — search_code is 1%
        for _ in range(99):
            monitor.record_proposal("analyse", "read_file")
        monitor.record_proposal("analyse", "search_code")
        # search_code = 1.0% which equals the threshold — NOT anomalous
        assert not monitor.is_anomalous("analyse", "search_code")

    def test_action_below_threshold_and_not_in_allowed_is_anomalous(self) -> None:
        monitor = BehavioralMonitor()
        for _ in range(_MIN_OBSERVATIONS):
            monitor.record_proposal("analyse", "read_file")
        # "delete_all" has 0% frequency and is not in allowed list
        assert monitor.is_anomalous("analyse", "delete_all", allowed_action_types=["read_file"])
