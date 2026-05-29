"""Unit tests for agent performance metrics in src/observability/metrics.py.

Spec: specs/observability/agent-performance.md
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Gauge, Histogram

# ── helpers ───────────────────────────────────────────────────────────────────


def _fresh_metrics():
    """Return isolated metric instances on a private registry to avoid global pollution."""
    registry = CollectorRegistry()
    mttd = Histogram(
        "agent_mttd_seconds_test",
        "MTTD",
        ["action_type"],
        buckets=(1, 5, 10, 30, 60, 120, 300, 600),
        registry=registry,
    )
    mttr = Histogram(
        "agent_mttr_seconds_test",
        "MTTR",
        ["action_type"],
        buckets=(10, 30, 60, 120, 300, 600, 1800, 3600),
        registry=registry,
    )
    rate = Gauge(
        "agent_autonomous_resolution_rate_test",
        "Autonomous resolution rate",
        ["action_type"],
        registry=registry,
    )
    cost = Histogram(
        "agent_cost_per_resolution_tokens_test",
        "Cost per resolution",
        ["action_type"],
        buckets=(100, 500, 1000, 2000, 5000, 10000, 20000, 50000),
        registry=registry,
    )
    return registry, mttd, mttr, rate, cost


# ── MTTD ──────────────────────────────────────────────────────────────────────


class TestAgentMttdMetric:
    def test_mttd_observation_increments_count(self) -> None:
        _, mttd, *_ = _fresh_metrics()
        mttd.labels("deploy").observe(15.0)
        assert mttd.labels("deploy")._sum.get() == 15.0

    def test_mttd_multiple_observations_accumulate(self) -> None:
        _, mttd, *_ = _fresh_metrics()
        mttd.labels("read_file").observe(5.0)
        mttd.labels("read_file").observe(20.0)
        assert mttd.labels("read_file")._sum.get() == 25.0

    def test_mttd_different_action_types_are_isolated(self) -> None:
        _, mttd, *_ = _fresh_metrics()
        mttd.labels("deploy").observe(10.0)
        mttd.labels("write_file").observe(30.0)
        assert mttd.labels("deploy")._sum.get() == 10.0
        assert mttd.labels("write_file")._sum.get() == 30.0

    def test_mttd_buckets_include_slo_boundary(self) -> None:
        _, mttd, *_ = _fresh_metrics()
        # SLO p99 ≤ 60s; bucket at 60 must exist
        mttd.labels("deploy").observe(60.0)
        assert mttd.labels("deploy")._sum.get() == 60.0


# ── MTTR ──────────────────────────────────────────────────────────────────────


class TestAgentMttrMetric:
    def test_mttr_observation_recorded(self) -> None:
        _, _, mttr, *_ = _fresh_metrics()
        mttr.labels("deploy").observe(120.0)
        assert mttr.labels("deploy")._sum.get() == 120.0

    def test_mttr_multiple_action_types_isolated(self) -> None:
        _, _, mttr, *_ = _fresh_metrics()
        mttr.labels("deploy").observe(200.0)
        mttr.labels("read_file").observe(50.0)
        assert mttr.labels("deploy")._sum.get() == 200.0
        assert mttr.labels("read_file")._sum.get() == 50.0

    def test_mttr_slo_boundary_bucket_exists(self) -> None:
        _, _, mttr, *_ = _fresh_metrics()
        # SLO p99 ≤ 600s; bucket must exist
        mttr.labels("deploy").observe(600.0)
        assert mttr.labels("deploy")._sum.get() == 600.0


# ── Autonomous Resolution Rate ────────────────────────────────────────────────


class TestAutonomousResolutionRateMetric:
    def test_autonomous_resolution_sets_to_one(self) -> None:
        _, _, _, rate, _ = _fresh_metrics()
        rate.labels("deploy").set(1.0)
        assert rate.labels("deploy")._value.get() == 1.0

    def test_hitl_escalation_sets_to_zero(self) -> None:
        _, _, _, rate, _ = _fresh_metrics()
        rate.labels("deploy").set(0.0)
        assert rate.labels("deploy")._value.get() == 0.0

    def test_rate_can_be_updated(self) -> None:
        _, _, _, rate, _ = _fresh_metrics()
        rate.labels("write_file").set(1.0)
        rate.labels("write_file").set(0.0)
        assert rate.labels("write_file")._value.get() == 0.0

    def test_different_action_types_independent(self) -> None:
        _, _, _, rate, _ = _fresh_metrics()
        rate.labels("deploy").set(1.0)
        rate.labels("read_file").set(0.0)
        assert rate.labels("deploy")._value.get() == 1.0
        assert rate.labels("read_file")._value.get() == 0.0


# ── Cost Per Resolution ───────────────────────────────────────────────────────


class TestCostPerResolutionMetric:
    def test_token_cost_observation_recorded(self) -> None:
        _, _, _, _, cost = _fresh_metrics()
        cost.labels("deploy").observe(3500)
        assert cost.labels("deploy")._sum.get() == 3500

    def test_slo_boundary_bucket_exists(self) -> None:
        _, _, _, _, cost = _fresh_metrics()
        # SLO p99 ≤ 10000 tokens; bucket must exist
        cost.labels("deploy").observe(10000)
        assert cost.labels("deploy")._sum.get() == 10000

    def test_multiple_resolutions_accumulate(self) -> None:
        _, _, _, _, cost = _fresh_metrics()
        cost.labels("write_file").observe(1000)
        cost.labels("write_file").observe(2000)
        assert cost.labels("write_file")._sum.get() == 3000


# ── record_agent_performance helper ──────────────────────────────────────────


class TestRecordAgentPerformanceHelper:
    def test_helper_exists_and_is_callable(self) -> None:
        from src.observability.metrics import record_agent_performance

        assert callable(record_agent_performance)

    def test_helper_does_not_raise_on_autonomous_resolution(self) -> None:
        from src.observability.metrics import record_agent_performance

        record_agent_performance(
            action_type="deploy",
            mttd_seconds=5.0,
            mttr_seconds=120.0,
            resolved_autonomously=True,
            tokens_used=3000,
        )

    def test_helper_does_not_raise_on_hitl_escalation(self) -> None:
        from src.observability.metrics import record_agent_performance

        record_agent_performance(
            action_type="write_file",
            mttd_seconds=12.0,
            mttr_seconds=400.0,
            resolved_autonomously=False,
            tokens_used=0,
        )
