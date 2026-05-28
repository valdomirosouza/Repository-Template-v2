# Skill — Capacity Planning

**Owner:** SRE Lead | **Reviewer:** Tech Lead | **Status:** Active | **Last updated:** 2026-05-28

Activate this skill when sizing resources, configuring HPA, evaluating scaling headroom,
or planning for traffic growth.

**Related:** `skills/sre/golden-signals.md`, `infrastructure/k8s/hpa.yaml`,
`infrastructure/helm/api-gateway/values.yaml`

---

## Key Capacity Signals

| Signal                  | Prometheus query                                                           | Scale-up trigger   |
| ----------------------- | -------------------------------------------------------------------------- | ------------------ |
| CPU utilisation         | `avg(rate(container_cpu_usage_seconds_total[5m])) by (pod)`                | >70% sustained     |
| Memory utilisation      | `container_memory_working_set_bytes / container_spec_memory_limit_bytes`   | >80%               |
| Agent semaphore waiting | `agent_semaphore_waiting`                                                  | >3 per pod average |
| Kafka consumer lag      | `kafka_consumer_lag`                                                       | >10 000 messages   |
| p99 latency             | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))` | >500 ms            |

---

## HPA Configuration

The HPA in `infrastructure/helm/api-gateway/templates/hpa.yaml` scales on CPU (primary)
and custom metrics (secondary). Key tuning knobs:

```yaml
autoscaling:
  minReplicas: 2 # never go below this — ensures HA
  maxReplicas: 10 # hard ceiling — prevents runaway cost
  targetCPUUtilizationPercentage: 70
```

**Stabilisation windows** prevent thrashing:

- Scale-up: 60 s window — reacts quickly to genuine load spikes
- Scale-down: 300 s window — conservative; allows queue drain before removing pods

**Scaling custom metrics** (requires prometheus-adapter):

- `agent_semaphore_waiting > 3` — agent concurrency saturation
- `kafka_consumer_lag > 5000` — consumer falling behind

---

## Sizing a New Service

Use this worksheet before the first production deploy:

**Step 1 — Baseline load estimate**

```
peak_rps = expected_peak_requests_per_second
p99_latency_s = target_p99_latency  # e.g. 0.5
concurrency = peak_rps × p99_latency_s  # Little's Law
```

**Step 2 — CPU request**

```
# Benchmark with k6 (tests/performance/k6/) to get actual CPU per request
cpu_per_request_millicores = (measured)
cpu_request = concurrency × cpu_per_request_millicores
cpu_limit = cpu_request × 4  # 4× headroom for bursts
```

**Step 3 — Memory request**

```
# Python: ~50 MB base + ~5 MB per concurrent request
memory_base_mb = 50
memory_request_mb = memory_base_mb + (concurrency × 5)
memory_limit_mb = memory_request_mb × 2
```

**Step 4 — Replica count**

```
min_replicas = max(2, ceil(cpu_request / cpu_per_pod_allocatable))
# Always ≥ 2 for HA across availability zones
```

---

## Resource Tuning in values.yaml

```yaml
resources:
  requests:
    cpu: 250m # guaranteed allocation — size for steady-state load
    memory: 256Mi # base + expected per-request overhead
  limits:
    cpu: 1000m # allow 4× burst before throttling
    memory: 512Mi # OOM-kill ceiling — size for peak + safety margin
```

**Common mistakes:**

- CPU request == CPU limit: eliminates bursting; causes throttling under load
- Memory limit < 2× request: frequent OOM kills on GC spikes (Python, JVM)
- minReplicas: 1: single point of failure; violates HA requirement

---

## Load Testing

Performance benchmarks live in `tests/performance/`. Run before any change to the
critical path (request pipeline, agent orchestrator, HITL gateway):

```bash
# k6 load test (requires k6 installed)
k6 run tests/performance/k6/<scenario>.js \
  -e BASE_URL=https://api.staging.example.com

# Target: p99 < 500ms at 2× expected peak RPS
```

Key k6 scenarios to cover:

1. Steady-state ramp: 0 → peak → 0 over 10 minutes
2. Spike: instant 10× load for 60 seconds
3. Soak: sustained 80% load for 30 minutes

---

## Error Budget and Capacity Link

If the service is approaching saturation (CPU >80%, p99 latency >500ms) **and** the
error budget is healthy (>50% remaining): scale up before the budget erodes.

If the error budget is already below 20%: treat capacity changes as emergency work
regardless of normal change process (see `docs/sre/slo/error-budget-policy.md`).
