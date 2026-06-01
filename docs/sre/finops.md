# FinOps — Budget Template and Cost-Allocation Guide

> **Status:** Active · **Version:** 1.0 · **Last updated:** 2026-05-31
> **Owner:** SRE Lead + Engineering Manager
> **Spec:** FIN-001 · **Related:** ADR-0020 · `docs/sre/slo/slo.yaml`

This document provides the actionable FinOps artefacts for this system: monthly budget templates, cost allocation tags, alert thresholds, optimization checklist, and the chargeback/showback model.

---

## 1. Cost Centers

Every cloud resource must be mapped to exactly one cost center.

| Cost Center ID | Name              | Owner               | Environments             |
| -------------- | ----------------- | ------------------- | ------------------------ |
| `CC-001`       | API Platform      | Engineering Manager | dev, staging, production |
| `CC-002`       | Data & Storage    | SRE Lead            | dev, staging, production |
| `CC-003`       | Observability     | SRE Lead            | staging, production      |
| `CC-004`       | CI/CD Pipeline    | DevOps Lead         | all                      |
| `CC-005`       | Security Tooling  | Security Lead       | all                      |
| `CC-006`       | AI / ML Workloads | AI Governance Lead  | staging, production      |

---

## 2. Monthly Budget Template

Adjust figures for your organization. Rows are services; columns are environments.

| Service                         | Dev (USD/mo) | Staging (USD/mo) | Production (USD/mo) | Total (USD/mo) |
| ------------------------------- | ------------ | ---------------- | ------------------- | -------------- |
| API Gateway (compute)           | 50           | 200              | 1,000               | 1,250          |
| PostgreSQL (managed DB)         | 30           | 120              | 600                 | 750            |
| Redis (cache)                   | 10           | 40               | 200                 | 250            |
| Kafka / message broker          | 20           | 80               | 400                 | 500            |
| Object storage (SBOM, logs)     | 5            | 20               | 100                 | 125            |
| Container registry              | 10           | 10               | 30                  | 50             |
| Observability (metrics, traces) | 20           | 80               | 400                 | 500            |
| CI/CD runners                   | 50           | 50               | 50                  | 150            |
| Security scanning (DAST, SCA)   | 20           | 20               | 20                  | 60             |
| **Total**                       | **215**      | **620**          | **2,800**           | **3,635**      |

> **Guidance:** Production budget should not exceed 10× dev budget without a capacity review. Staging should be ≥ 20% of production to catch sizing issues before promotion.

---

## 3. Required Cost Allocation Tags

Every cloud resource (VMs, managed services, storage buckets, load balancers) **must** carry all five required tags. Missing tags trigger a `cost-tag-compliance` alert in the observability stack.

| Tag Key               | Required    | Example Values                       | Purpose                 |
| --------------------- | ----------- | ------------------------------------ | ----------------------- |
| `env`                 | ✅          | `dev`, `staging`, `production`       | Environment separation  |
| `service`             | ✅          | `api-gateway`, `event-worker`        | Maps to `services.yaml` |
| `cost-center`         | ✅          | `CC-001` … `CC-006`                  | Chargeback routing      |
| `team`                | ✅          | `platform`, `stream-payments`        | Team-level showback     |
| `managed-by`          | ✅          | `terraform`, `helm`, `manual`        | IaC traceability        |
| `data-classification` | Recommended | `public`, `internal`, `confidential` | Governance              |

### Enforcement

Add this to every Terraform module and Helm values file:

```hcl
# terraform — required tags
locals {
  required_tags = {
    env             = var.environment
    service         = var.service_name
    cost-center     = var.cost_center_id
    team            = var.team_name
    managed-by      = "terraform"
  }
}
```

```yaml
# helm values — pod labels propagated to cloud billing
commonLabels:
  env: production
  service: api-gateway
  cost-center: CC-001
  team: platform
  managed-by: helm
```

---

## 4. Budget Alert Thresholds

| Threshold                       | Level       | Action                                                                  |
| ------------------------------- | ----------- | ----------------------------------------------------------------------- |
| 70% of monthly budget consumed  | ⚠️ Warning  | Notify Engineering Manager + SRE Lead via Slack `#cost-alerts`          |
| 90% of monthly budget consumed  | 🔴 Critical | Page on-call SRE; review active deployments for cost anomalies          |
| 100% of monthly budget consumed | 🚨 Block    | New production deployments require EM approval; auto-scale-out disabled |
| 120% of monthly budget consumed | 🚨 Escalate | CFO + CTO notified; incident opened in incident tracker                 |

### Prometheus alert rules (example)

```yaml
# infrastructure/monitoring/prometheus/cost-alerts.yaml
groups:
  - name: finops
    rules:
      - alert: BudgetWarning
        expr: cloud_cost_monthly_usd / cloud_budget_monthly_usd > 0.70
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Cost at {{ $value | humanizePercentage }} of monthly budget"

      - alert: BudgetCritical
        expr: cloud_cost_monthly_usd / cloud_budget_monthly_usd > 0.90
        for: 30m
        labels:
          severity: critical
        annotations:
          summary: "Cost at {{ $value | humanizePercentage }} of monthly budget — page on-call"
```

---

## 5. Cloud Cost Optimization Checklist

Run this checklist monthly during the cost review (§7).

### Compute

- [ ] Right-size instances: p99 CPU < 60% and p99 memory < 70% over 7 days → downsize one tier
- [ ] Use spot/preemptible instances for dev and CI/CD workloads (≥ 50% cost reduction)
- [ ] Terminate idle dev instances after 8 hours of zero traffic
- [ ] Use committed-use discounts (1-year CUD) for stable production workloads ≥ 3 months old

### Storage

- [ ] Enable lifecycle policies: move logs to cold storage after 30 days; delete after 90 days (unless SOX retention applies — 7 years)
- [ ] Delete unattached persistent disks weekly (automated via IaC `make clean-orphaned-disks`)
- [ ] Use tiered storage for SBOM artifacts: hot for 7 days, cold thereafter

### Networking

- [ ] Route internal service-to-service traffic through private VPC (avoid egress charges)
- [ ] Enable CDN for frontend static assets (reduces origin compute and egress)
- [ ] Review NAT gateway data processing charges monthly — high volume may justify a private link

### Observability

- [ ] Set log retention to 30 days in dev, 90 days in staging, 1 year in production
- [ ] Sample traces at 100% in dev/staging, 10% in production (configurable via OTel SDK)
- [ ] Archive Prometheus metrics beyond 15 days to object storage (Thanos/Cortex)

### CI/CD

- [ ] Use ephemeral runners (terminate after job completion) — no idle time charges
- [ ] Cache Docker layers and uv/pip/npm dependencies between runs (reduces build minutes 40–60%)

---

## 6. Chargeback and Showback Model

| Model          | Description                                                   | When to use                                                                  |
| -------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Showback**   | Cost reports distributed to teams; no actual billing transfer | Recommended default — builds cost awareness without financial friction       |
| **Chargeback** | Actual cloud costs charged back to team's budget              | Use when teams operate as independent P&Ls or to enforce hard accountability |

### Showback report cadence

Monthly report delivered to each team by the 5th of the following month:

- Total spend by cost center
- Month-over-month delta (%)
- Top 3 cost drivers
- Optimization opportunities identified

Template: `docs/sre/finops-monthly-report-YYYY-MM.md` (generated from observability data).

---

## 7. FinOps Maturity Self-Assessment

Rate your organization on each dimension: **Crawl** (0) → **Walk** (1) → **Run** (2).

| Dimension        | Crawl                     | Walk                             | Run                                       |
| ---------------- | ------------------------- | -------------------------------- | ----------------------------------------- |
| **Visibility**   | No cost data              | Showback reports exist           | Real-time cost dashboards                 |
| **Allocation**   | Shared account only       | Tags enforced                    | Full chargeback by team                   |
| **Optimization** | Ad-hoc only               | Monthly checklist run            | Automated right-sizing                    |
| **Governance**   | No budget                 | Budgets set per env              | Budgets + auto-alerts + deployment gates  |
| **Culture**      | Engineers unaware of cost | Cost awareness in sprint reviews | Cost is a first-class feature requirement |

Target: all dimensions at **Walk** before first production launch; **Run** within 6 months.

---

## 8. Cost Review Cadence

| Cadence   | Activity                                                                              | Owner         |
| --------- | ------------------------------------------------------------------------------------- | ------------- |
| Weekly    | Review `#cost-alerts` Slack channel; acknowledge anomalies                            | On-call SRE   |
| Monthly   | Run optimization checklist (§5); distribute showback report                           | SRE Lead      |
| Quarterly | Review budgets vs actuals; adjust next-quarter budget; update committed-use discounts | EM + SRE Lead |
| Annually  | Full FinOps maturity assessment; renegotiate cloud contracts                          | EM + CFO      |
