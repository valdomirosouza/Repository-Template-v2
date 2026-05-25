"""Unit tests for src/observability/metrics.py — gauge and helper functions.

Spec: specs/system/architecture.md (Quality Attributes — Observable-by-default)
ADR:  ADR-0004 (Observability Stack)
"""

from src.observability.metrics import (
    LLM_TOKEN_BUDGET,
    init_budget_gauge,
)


class TestBudgetGauge:
    def test_init_budget_gauge_sets_value(self):
        init_budget_gauge("test-service", 500_000)
        sample = LLM_TOKEN_BUDGET.labels("test-service")
        assert sample._value.get() == 500_000

    def test_init_budget_gauge_overwrites_previous_value(self):
        init_budget_gauge("test-service", 1_000_000)
        init_budget_gauge("test-service", 2_000_000)
        sample = LLM_TOKEN_BUDGET.labels("test-service")
        assert sample._value.get() == 2_000_000

    def test_init_budget_gauge_different_services_are_independent(self):
        init_budget_gauge("service-a", 100_000)
        init_budget_gauge("service-b", 999_999)
        assert LLM_TOKEN_BUDGET.labels("service-a")._value.get() == 100_000
        assert LLM_TOKEN_BUDGET.labels("service-b")._value.get() == 999_999
