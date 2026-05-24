# Error Budget Policy

**Owner:** SRE Lead | **Last reviewed:** 2026-05-24

---

## What is an Error Budget?

An error budget is the maximum allowed unreliability within an SLO window.

```
Error budget = (1 − SLO target) × window duration
```

| Service                    | SLO   | Window | Monthly budget (minutes) |
| -------------------------- | ----- | ------ | ------------------------ |
| api-gateway availability   | 99.9% | 30d    | 43.8 min                 |
| api-gateway latency p99    | 500ms | 30d    | N/A (threshold-based)    |
| agent-service success rate | 99.5% | 30d    | 216 min                  |
| event-consumer processing  | 99.9% | 30d    | 43.8 min                 |

---

## Policy Tiers

| Remaining Budget | Policy                                                                                             | Owner action required                      |
| ---------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| > 50%            | Normal development velocity                                                                        | None                                       |
| 25–50%           | Elevated monitoring; review recent changes for contributing factors                                | SRE Lead reviews weekly                    |
| 10–25%           | **Feature freeze** for the affected service; reliability work prioritised over features            | SRE Lead + Tech Lead align on freeze scope |
| < 10%            | **Full feature freeze**; no production deploys without SRE Lead sign-off; incident review required | SRE Lead escalates to Engineering Manager  |
| 0% (exhausted)   | Emergency response; post-mortem mandatory within 48h; CAB review before any deploy                 | Engineering Manager notified; CAB convened |

---

## Burn Rate Alerts

Two complementary alert windows detect both fast and slow budget exhaustion:

| Alert     | Window | Burn rate | Meaning                                 | Severity |
| --------- | ------ | --------- | --------------------------------------- | -------- |
| Fast burn | 1h     | 14.4×     | Budget consumed in ~2 days at this rate | Critical |
| Slow burn | 6h     | 6.0×      | Budget consumed in ~5 days at this rate | Warning  |

Both alerts must fire and resolve cleanly for the on-call to clear an incident.

---

## Budget Replenishment

Error budgets reset at the start of each rolling 30-day window. There is no
carry-forward of unused budget across windows.

---

## Review Cadence

| Review                 | Frequency                       | Owner                          |
| ---------------------- | ------------------------------- | ------------------------------ |
| Error budget status    | Weekly (SRE sync)               | SRE Lead                       |
| SLO target review      | Quarterly                       | SRE Lead + Tech Lead           |
| Policy tier adjustment | As needed after major incidents | SRE Lead + Engineering Manager |

---

## Escalation Path

```
SLO breach alert fires
      ↓
On-call engineer investigates (runbook)
      ↓
Budget < 10% → SRE Lead notified
      ↓
Budget exhausted → Engineering Manager notified → CAB review before next deploy
```
