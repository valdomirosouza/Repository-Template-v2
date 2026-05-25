# Skill — Golden Signals

**Owner:** SRE Lead | **Reviewer:** Tech Lead | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill for any observability work, SLO monitoring, alert triage, or on-call response.

---

## The Four Golden Signals

| Signal         | Definition                                         | Primary metric                                                                   |
| -------------- | -------------------------------------------------- | -------------------------------------------------------------------------------- |
| **Traffic**    | Volume of requests the system is serving           | `rate(http_requests_total[5m])`                                                  |
| **Error Rate** | Fraction of requests that are failing              | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])`   |
| **Saturation** | How full the service is — CPU, memory, queue depth | `node_cpu_seconds_total`, `kafka_consumer_lag`, `node_memory_MemAvailable_bytes` |
| **Latency**    | Time to serve a request — p50, p95, p99            | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))`       |

A signal breach means the service is degraded. Two or more signal breaches simultaneously = SLO at risk.

---

## Dashboard

Primary dashboard: `infrastructure/monitoring/grafana/dashboards/golden-signals.json`
SRE overview (SLO + error budget): `infrastructure/monitoring/grafana/dashboards/sre-overview.json`

---

## Alert Thresholds

| Alert                  | Threshold              | Severity | Action                            |
| ---------------------- | ---------------------- | -------- | --------------------------------- |
| `ZeroRequestRate`      | 0 req/s for 3 min      | Critical | Page on-call immediately          |
| `CriticalErrorRate`    | >5% 5xx for 2 min      | Critical | Page on-call; consider rollback   |
| `HighErrorRate`        | >1% 5xx for 5 min      | Warning  | Investigate; prepare rollback     |
| `CriticalP99Latency`   | p99 >2s for 2 min      | Critical | Page on-call; check saturation    |
| `HighP99Latency`       | p99 >500ms for 5 min   | Warning  | Check saturation and upstream     |
| `KafkaConsumerLagHigh` | lag >10k for 5 min     | Warning  | Check consumers; may need scaling |
| `HighCPUUsage`         | CPU >80% for 10 min    | Warning  | Consider HPA scale-up             |
| `HighMemoryUsage`      | Memory >85% for 10 min | Warning  | Check for memory leaks            |

Full alert definitions: `infrastructure/monitoring/prometheus/rules/golden-signals.yaml`

---

## On-Call Triage Checklist

When paged, follow this order:

1. **Check Traffic** — is the request rate normal, zero, or spiking?
   - Zero: service is down or unreachable — check pod status, network, upstream
   - Spike: possible DDoS or upstream retry storm — check rate limiting

2. **Check Error Rate** — what % of requests are failing?
   - > 5%: high-impact; initiate rollback evaluation immediately
   - 1–5%: elevated; investigate root cause before deciding on rollback

3. **Check Saturation** — is the service resource-constrained?
   - CPU/memory: check pod resource requests/limits; consider HPA
   - Kafka lag: check consumer pod health; may need partition scaling

4. **Check Latency** — is p99 degraded?
   - If latency high + saturation high: resource exhaustion — scale or shed load
   - If latency high + saturation normal: upstream dependency slow — check LLM provider, DB

5. **Correlate with recent deploys** — run `helm history app -n production` to check timing

6. **Decide: Investigate or Rollback?**
   - If root cause clear and fix is quick (<15 min): fix forward
   - If root cause unclear or fix >15 min: rollback immediately, investigate after

---

## SLO Breach Escalation

If error budget drops below 10%:

- Feature releases are **blocked** (see `docs/sre/slo/error-budget-policy.md`)
- Page Engineering Manager
- Open incident and begin post-mortem scheduling

Runbooks: `docs/runbooks/rollback-procedure.md`, `docs/runbooks/disaster-recovery.md`
