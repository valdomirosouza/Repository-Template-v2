# Skill: DORA Metrics

## Purpose

Track, enforce, and improve the four DORA metrics to achieve and maintain Elite performance tier.

## When to Activate

- Any CI/CD pipeline modification
- Any production deployment work
- Monthly SRE review or retrospective
- Any change to `cd-production.yml` or `cd-staging.yml`
- MTTR post-incident review

## Elite Tier Targets

| Metric                 | Elite Target                       | Prometheus Metric          |
| ---------------------- | ---------------------------------- | -------------------------- |
| Deployment Frequency   | ≥ 1/day (staging), ≥ 1/week (prod) | `dora_deployments_total`   |
| Lead Time for Changes  | p50 ≤ 24h commit → production      | `dora_lead_time_seconds`   |
| Change Failure Rate    | < 5%                               | `dora_change_failure_rate` |
| Time to Restore (MTTR) | p50 < 1h                           | `dora_mttr_seconds`        |

## Prometheus Metrics

Defined in `src/observability/dora_metrics.py`:

```python
from prometheus_client import Counter, Gauge, Histogram

dora_deployments_total = Counter(
    "dora_deployments_total",
    "Total deployments by outcome",
    ["service", "environment", "outcome"]  # outcome: success | rollback | failure
)

dora_lead_time_seconds = Histogram(
    "dora_lead_time_seconds",
    "Lead time from first commit to production deploy",
    ["service"],
    buckets=[3600, 7200, 14400, 28800, 86400, 172800]  # 1h → 48h
)

dora_change_failure_rate = Gauge(
    "dora_change_failure_rate",
    "Rolling 30-day change failure rate (0.0–1.0)",
    ["service"]
)

dora_mttr_seconds = Histogram(
    "dora_mttr_seconds",
    "Time to restore service after failure",
    ["service"],
    buckets=[600, 1800, 3600, 7200, 14400]  # 10min → 4h
)
```

## cd-production.yml Integration

The `emit-dora-event` job runs after every production deploy:

```yaml
- name: Emit DORA deployment event
  run: |
    python3 - << 'EOF'
    import os, time, requests

    outcome = os.environ.get("DEPLOY_OUTCOME", "success")
    service = os.environ.get("SERVICE_NAME", "api-gateway")
    first_commit_ts = float(os.environ.get("FIRST_COMMIT_TIMESTAMP", time.time()))
    lead_time = time.time() - first_commit_ts

    pushgateway = os.environ["PROMETHEUS_PUSHGATEWAY_URL"]
    metrics = f"""
# HELP dora_deployments_total Total deployments by outcome
# TYPE dora_deployments_total counter
dora_deployments_total{{service="{service}",environment="production",outcome="{outcome}"}} 1

# HELP dora_lead_time_seconds Lead time from first commit to production deploy
# TYPE dora_lead_time_seconds histogram
dora_lead_time_seconds_sum{{service="{service}"}} {lead_time}
dora_lead_time_seconds_count{{service="{service}"}} 1
"""
    requests.post(f"{pushgateway}/metrics/job/dora", data=metrics)
    print(f"DORA event emitted: outcome={outcome}, lead_time={lead_time:.0f}s")
    EOF
  env:
    DEPLOY_OUTCOME: ${{ steps.deploy.outcome }}
    SERVICE_NAME: ${{ inputs.service || 'api-gateway' }}
    FIRST_COMMIT_TIMESTAMP: ${{ steps.first-commit.outputs.timestamp }}
    PROMETHEUS_PUSHGATEWAY_URL: ${{ vars.PROMETHEUS_PUSHGATEWAY_URL }}
```

## Grafana Dashboard

Dashboard at `infrastructure/monitoring/grafana/dora-metrics.json` — four panels:

- **Deployment Frequency**: bar chart, 30-day rolling, by environment
- **Lead Time**: p50/p90 histogram with Elite/High/Medium/Low threshold annotations
- **Change Failure Rate**: gauge (0–20%) with 5% Elite threshold line
- **MTTR**: p50/p90 time series with 1h Elite threshold line

## Monthly DORA Report

Generate `docs/sre/dora-report-YYYY-MM.md` at the start of each month using the template in `specs/observability/dora-metrics.md §5`. SRE Lead reviews; if any metric falls below Elite tier, schedule retrospective within 5 business days.

## Retrospective Trigger

Any DORA metric falling below Elite → Medium threshold requires:

1. Retrospective scheduled within 5 business days
2. Root cause identified and documented
3. Improvement action assigned with owner and due date
4. Follow-up in next monthly report

## Spec Reference

`specs/observability/dora-metrics.md` — metric definitions, tier thresholds, dashboard spec, alerting rules, acceptance criteria.
