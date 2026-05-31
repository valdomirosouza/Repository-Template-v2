"""DORA metrics — four key engineering effectiveness counters/histograms.

Emitted by the CI/CD pipeline via Prometheus Pushgateway.
See specs/observability/dora-metrics.md and ADR-0028 for full spec.
"""

from prometheus_client import Counter, Gauge, Histogram

dora_deployments_total = Counter(
    "dora_deployments_total",
    "Total deployments by outcome",
    ["service", "environment", "outcome"],  # outcome: success | rollback | failure
)

dora_lead_time_seconds = Histogram(
    "dora_lead_time_seconds",
    "Lead time from first commit to production deploy",
    ["service"],
    buckets=[3_600, 7_200, 14_400, 28_800, 86_400, 172_800],  # 1h → 48h
)

dora_change_failure_rate = Gauge(
    "dora_change_failure_rate",
    "Rolling 30-day change failure rate (0.0-1.0)",
    ["service"],
)

dora_mttr_seconds = Histogram(
    "dora_mttr_seconds",
    "Time to restore service after failure",
    ["service"],
    buckets=[600, 1_800, 3_600, 7_200, 14_400],  # 10min → 4h
)
