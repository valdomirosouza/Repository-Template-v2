# ADR-0028 — DORA Metrics Instrumentation

**Status:** Accepted
**Date:** 2026-05-31
**Authors:** SRE Lead, DevOps Lead
**Reviewers:** Tech Lead

---

## Context

DORA (DevOps Research and Assessment) metrics are the industry-standard KPIs for engineering effectiveness. The repository currently has no systematic measurement of Deployment Frequency, Lead Time for Changes, Change Failure Rate, or Time to Restore Service (MTTR). Without these metrics, it is impossible to demonstrate Elite-tier performance or identify regression trends.

The existing Prometheus/Grafana stack (see observability architecture in CLAUDE.md §0.1) provides the collection and visualization infrastructure; it simply needs the DORA-specific metrics to be emitted.

---

## Decision

Emit four DORA metrics from the CI/CD pipeline using Prometheus counters, gauges, and histograms defined in `src/observability/dora_metrics.py`. The Prometheus Pushgateway (already in the infrastructure stack) receives pipeline events; long-running services emit via the standard OTel SDK path.

**Metric definitions:**

| Metric                     | Type      | Labels                        | Measurement                                                     |
| -------------------------- | --------- | ----------------------------- | --------------------------------------------------------------- |
| `dora_deployments_total`   | Counter   | service, environment, outcome | Incremented on every deploy (outcome: success/rollback/failure) |
| `dora_lead_time_seconds`   | Histogram | service                       | First commit SHA timestamp → production deploy timestamp        |
| `dora_change_failure_rate` | Gauge     | service                       | 30-day rolling: rollback+failure deploys / total deploys        |
| `dora_mttr_seconds`        | Histogram | service                       | Incident-opened timestamp → service-restored timestamp          |

**Elite tier targets** (enforced via Prometheus alerting rules):

- Deployment Frequency: ≥ 1/day to staging, ≥ 1/week to production
- Lead Time: ≤ 24h (p50)
- Change Failure Rate: < 5%
- MTTR: < 1h (p50)

**Lead time measurement:** the `cd-production.yml` `emit-dora-event` job reads the PR's first-commit timestamp from the GitHub API and calculates elapsed seconds to the deploy timestamp. This is pushed to the Prometheus Pushgateway.

**Dashboard:** `infrastructure/monitoring/grafana/dora-metrics.json` auto-provisioned via the existing Grafana provisioning mechanism.

**Monthly report:** generated from `docs/sre/dora-report-YYYY-MM.md` template; SRE Lead responsible for review and retrospective if any metric falls below Elite threshold.

---

## Consequences

- `cd-production.yml` gains an `emit-dora-event` job that pushes metrics after every deploy
- Prometheus Pushgateway must be reachable from GitHub Actions runners (network policy update required for self-hosted runners)
- `src/observability/dora_metrics.py` adds four metric registrations to the existing metrics module
- Monthly DORA retrospective required if any metric falls below Elite threshold
- `dora_mttr_seconds` requires incident management tooling integration; initially measured manually via incident ticket timestamps until automated integration is added

---

## Alternatives Considered

**Third-party DORA SaaS (FAIRO, LinearB, etc.)** — valid for large orgs; deferred. Current Prometheus-native approach avoids additional vendor dependencies and keeps metrics co-located with the existing observability stack.

**GitHub Insights only** — rejected as insufficient; does not cover MTTR and change failure rate as defined by DORA research.
