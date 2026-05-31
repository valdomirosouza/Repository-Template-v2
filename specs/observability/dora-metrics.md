# DORA Metrics Instrumentation — Specification

**ID:** SPEC-dora-metrics
**Version:** 1.0.0
**Status:** Approved
**Owner:** SRE Lead
**ADR:** ADR-0028

---

## 1. Purpose

Define the instrumentation, collection, and reporting requirements for the four DORA metrics, enabling Elite-tier engineering effectiveness measurement and continuous improvement.

---

## 2. Metric Definitions

### 2.1 Deployment Frequency

**Definition:** Number of successful deployments to production per unit time.

| Prometheus metric | `dora_deployments_total`                                           |
| ----------------- | ------------------------------------------------------------------ |
| Type              | Counter                                                            |
| Labels            | `service`, `environment`, `outcome` (success / rollback / failure) |
| Emitted by        | `cd-production.yml` `emit-dora-event` job                          |

**Elite target:** ≥ 1 deploy/day to staging; ≥ 1 deploy/week to production.

### 2.2 Lead Time for Changes

**Definition:** Elapsed time from the first commit on a PR to the production deployment of that PR.

| Prometheus metric | `dora_lead_time_seconds`                           |
| ----------------- | -------------------------------------------------- |
| Type              | Histogram                                          |
| Labels            | `service`                                          |
| Buckets           | 3600, 7200, 14400, 28800, 86400, 172800 (1h → 48h) |
| Emitted by        | `cd-production.yml` `emit-dora-event` job          |

**Calculation:** `production_deploy_timestamp - first_commit_timestamp_on_pr`. First commit timestamp retrieved from GitHub API using the PR's head SHA and merge commit.

**Elite target:** p50 ≤ 24h.

### 2.3 Change Failure Rate

**Definition:** Percentage of production deployments that result in a rollback or emergency hotfix within 24h.

| Prometheus metric | `dora_change_failure_rate`                                      |
| ----------------- | --------------------------------------------------------------- |
| Type              | Gauge                                                           |
| Labels            | `service`                                                       |
| Window            | 30-day rolling                                                  |
| Calculation       | `(rollback_count + failure_count) / total_deploys` over 30 days |
| Updated by        | `cd-production.yml` `emit-dora-event` job after each deploy     |

**Elite target:** < 5%.

### 2.4 Time to Restore Service (MTTR)

**Definition:** Elapsed time from the opening of a production incident ticket to service restoration (as marked by the on-call engineer).

| Prometheus metric | `dora_mttr_seconds`                                            |
| ----------------- | -------------------------------------------------------------- |
| Type              | Histogram                                                      |
| Labels            | `service`                                                      |
| Buckets           | 600, 1800, 3600, 7200, 14400 (10min → 4h)                      |
| Emitted by        | Incident management tooling or manual push via Makefile target |

**Elite target:** p50 < 1h.

---

## 3. Tier Thresholds

| Metric               | Elite   | High         | Medium         | Low       |
| -------------------- | ------- | ------------ | -------------- | --------- |
| Deployment Frequency | > 1/day | 1/week–1/day | 1/month–1/week | < 1/month |
| Lead Time            | < 1h    | 1 day–1 week | 1 week–1 month | > 1 month |
| Change Failure Rate  | 0–5%    | 5–10%        | 10–15%         | > 15%     |
| MTTR                 | < 1h    | < 1 day      | 1 day–1 week   | > 1 week  |

---

## 4. Grafana Dashboard Specification

File: `infrastructure/monitoring/grafana/dora-metrics.json`
Provisioned via: `infrastructure/monitoring/grafana/provisioning/`

| Panel                | Visualization             | Query                                                                     |
| -------------------- | ------------------------- | ------------------------------------------------------------------------- |
| Deployment Frequency | Bar chart, 30-day rolling | `increase(dora_deployments_total{outcome="success"}[30d])`                |
| Lead Time p50/p90    | Stat + time series        | `histogram_quantile(0.50/0.90, rate(dora_lead_time_seconds_bucket[30d]))` |
| Change Failure Rate  | Gauge (0–20%)             | `dora_change_failure_rate` with 5% threshold annotation                   |
| MTTR p50/p90         | Stat + time series        | `histogram_quantile(0.50/0.90, rate(dora_mttr_seconds_bucket[30d]))`      |

Each panel annotated with Elite/High/Medium/Low threshold lines.

---

## 5. Monthly Report Template

Stored at `docs/sre/dora-report-YYYY-MM.md`:

```markdown
# DORA Report — YYYY-MM

| Metric               | Result         | Target                         | Tier                  |
| -------------------- | -------------- | ------------------------------ | --------------------- |
| Deployment Frequency | X deploys/week | ≥ 1/day staging, ≥ 1/week prod | Elite/High/Medium/Low |
| Lead Time p50        | Xh             | ≤ 24h                          | Elite/High/Medium/Low |
| Lead Time p90        | Xh             | —                              | —                     |
| Change Failure Rate  | X%             | < 5%                           | Elite/High/Medium/Low |
| MTTR p50             | Xmin           | < 1h                           | Elite/High/Medium/Low |
| MTTR p90             | Xmin           | —                              | —                     |

## Overall Tier: Elite / High / Medium / Low

## Actions (required if any metric < Elite)

- [ ] Retrospective scheduled within 5 business days
- [ ] Root cause identified
- [ ] Improvement action with owner and due date
```

---

## 6. Alerting Rules

Add to `infrastructure/monitoring/alerts/dora-alerts.yaml`:

- Alert when `dora_change_failure_rate > 0.10` (Medium threshold) for 24h → PagerDuty warning
- Alert when `dora_lead_time_seconds{quantile="0.5"} > 86400` (> 24h) for 7 days → Slack #eng-metrics
- Alert when no `dora_deployments_total` increments for 14 days → Slack #eng-metrics

---

## 7. Acceptance Criteria

- [ ] All four DORA metrics queryable from Prometheus
- [ ] Grafana dashboard renders with correct panels and threshold annotations
- [ ] Monthly report template generatable from Prometheus query results
- [ ] `cd-production.yml` `emit-dora-event` job runs after every deploy and pushes metrics
- [ ] Alert rules present in `infrastructure/monitoring/alerts/dora-alerts.yaml`
- [ ] Any metric falling below Elite threshold triggers a documented retrospective within 5 business days
