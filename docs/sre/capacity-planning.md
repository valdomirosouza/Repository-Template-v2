# Capacity Planning Template

> **Status:** Active · **Version:** 1.0 · **Last updated:** 2026-05-31
> **Owner:** SRE Lead
> **Spec:** CAP-001 · **Related:** `docs/sre/slo/slo.yaml` · `docs/sre/deployment-strategy.md`

This template guides resource sizing, headroom planning, and scaling decisions for every service in the monorepo. Complete a copy of §4 (Capacity Worksheet) for each service before its first production promotion.

---

## 1. Resource Sizing Baselines

Starting baselines per language runtime at **p99 load**. Adjust based on profiling data.

| Runtime                    | CPU Request | CPU Limit | Memory Request | Memory Limit | Notes                                          |
| -------------------------- | ----------- | --------- | -------------- | ------------ | ---------------------------------------------- |
| Python / FastAPI           | 250m        | 1000m     | 256 Mi         | 512 Mi       | Async I/O; scale horizontal before vertical    |
| Java / Spring Boot         | 500m        | 2000m     | 512 Mi         | 1024 Mi      | JVM warm-up; allow 90s readiness probe timeout |
| Go                         | 100m        | 500m      | 64 Mi          | 128 Mi       | Low overhead; check goroutine count under load |
| Node.js / Next.js (SSR)    | 200m        | 800m      | 256 Mi         | 512 Mi       | Event loop; watch for GC pauses > 50ms         |
| Node.js / Next.js (static) | 50m         | 200m      | 64 Mi          | 128 Mi       | Serve from CDN where possible                  |

> **Rule:** `requests` = baseline at p50 load. `limits` = 2× requests for most services, 4× for Java (JVM burst). Never set `limits` < `requests`.

---

## 2. Headroom Rules

Headroom prevents saturation during unexpected traffic spikes. Measure headroom at **p99 load over the last 7 days**.

| Resource                  | Minimum Headroom  | Action when breached                                 |
| ------------------------- | ----------------- | ---------------------------------------------------- |
| CPU                       | ≥ 30% free        | Scale out (add replicas) or upsize CPU limit         |
| Memory                    | ≥ 20% free        | Upsize memory limit; investigate for leaks if sudden |
| Disk (persistent volumes) | ≥ 25% free        | Expand PVC or archive/purge old data                 |
| Open file descriptors     | ≥ 40% of `ulimit` | Tune `ulimit` and check for connection leaks         |
| DB connection pool        | ≥ 30% free        | Scale connection pool or add read replicas           |
| Kafka consumer lag        | < 1 min at peak   | Add consumer replicas or increase partition count    |

### Prometheus headroom alerts

```yaml
# infrastructure/monitoring/prometheus/capacity-alerts.yaml
groups:
  - name: capacity
    rules:
      - alert: CPUHeadroomLow
        expr: |
          1 - (rate(container_cpu_usage_seconds_total[5m]) /
               kube_pod_container_resource_limits{resource="cpu"}) < 0.30
        for: 15m
        labels:
          severity: warning

      - alert: MemoryHeadroomLow
        expr: |
          1 - (container_memory_working_set_bytes /
               kube_pod_container_resource_limits{resource="memory"}) < 0.20
        for: 15m
        labels:
          severity: warning
```

---

## 3. Horizontal vs Vertical Scaling Decision Matrix

| Condition                                  | Decision                                    | Rationale                                               |
| ------------------------------------------ | ------------------------------------------- | ------------------------------------------------------- |
| CPU headroom < 30%, memory headroom ≥ 30%  | Scale **out** (add replicas)                | CPU-bound; stateless service benefits from distribution |
| Memory headroom < 20%, CPU headroom ≥ 30%  | Scale **up** (increase memory limit)        | Memory-bound; adding replicas doesn't help              |
| Both CPU and memory headroom low           | Scale **out first**, then review limits     | Likely sustained load increase                          |
| Single request p99 latency > SLO threshold | Scale **up** CPU limit                      | Individual request bottleneck; parallelism won't help   |
| DB connection pool exhausted               | Add **read replicas** or increase pool size | DB is the bottleneck, not compute                       |
| Kafka consumer lag growing                 | Scale **out** consumers                     | Partition-parallel processing                           |
| Service is stateful (sticky sessions)      | Scale **up** only, or redesign              | Horizontal scaling requires session externalization     |

### HPA configuration template

```yaml
# infrastructure/helm/<service>/templates/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: { { .Release.Name } }
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: { { .Release.Name } }
  minReplicas: { { .Values.hpa.minReplicas | default 2 } }
  maxReplicas: { { .Values.hpa.maxReplicas | default 10 } }
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 65 # trigger before headroom < 30%
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 75 # trigger before headroom < 20%
```

---

## 4. Capacity Worksheet (complete per service)

Copy and fill in this section for each service before production promotion.

```
Service name:          __________________________
Language runtime:      __________________________
Date completed:        __________________________
Completed by:          __________________________
Reviewed by (SRE):     __________________________

### Current traffic profile (from load test or production data)
Peak RPS:              __________________________
P50 latency:           __________________________ ms
P99 latency:           __________________________ ms
P50 CPU usage:         __________________________ millicores
P99 CPU usage:         __________________________ millicores
P50 memory usage:      __________________________ MiB
P99 memory usage:      __________________________ MiB

### Kubernetes resource settings
CPU request:           __________________________ (≥ p50 CPU)
CPU limit:             __________________________ (≥ p99 CPU + 30% headroom)
Memory request:        __________________________ (≥ p50 memory)
Memory limit:          __________________________ (≥ p99 memory + 20% headroom)
Min replicas:          __________________________
Max replicas:          __________________________
HPA CPU trigger:       __________________________ % (recommend 65%)
HPA memory trigger:    __________________________ % (recommend 75%)

### Growth projection (next 6 months)
Expected peak RPS growth: __________________________ %
Projected peak RPS:       __________________________
Resource adjustment needed: ______________________

### Load test sign-off
Load test run date:        __________________________
Peak RPS tested:           __________________________
Pass/Fail:                 __________________________
```

---

## 5. Traffic Growth Model

Use this formula to project resource needs:

```
projected_peak_rps = current_peak_rps × (1 + monthly_growth_rate)^months

# Example: 100 RPS today, 10% monthly growth over 6 months
# 100 × (1.10)^6 = 177 RPS
```

Size for the **6-month projected peak** at initial deployment. Revisit quarterly.

For services with seasonal traffic (e.g., payment processing with end-of-month spikes), apply a **seasonality multiplier** on top of the growth projection:

```
capacity_target = projected_peak_rps × seasonality_multiplier × 1.30   # 30% headroom
```

---

## 6. Load Testing Prerequisites

A service **must** pass load testing before its first production promotion. Minimum requirements:

- [ ] Load test runs at **2× expected peak RPS** for ≥ 30 minutes without errors
- [ ] P99 latency remains within the SLO target (`docs/sre/slo/slo.yaml`) throughout
- [ ] Memory usage is stable (no upward trend — rules out memory leak)
- [ ] CPU usage stays below the HPA trigger threshold at 1× peak RPS
- [ ] No circuit-breaker trips or connection pool exhaustion observed
- [ ] Graceful degradation tested: upstream dependency killed mid-test — service returns 503, not 500
- [ ] Load test report committed to `docs/sre/load-tests/<service>-YYYY-MM-DD.md`

Recommended tool: [k6](https://k6.io) — scripts in `tests/load/`.

---

## 7. Quarterly Capacity Review

Run this review for each production service every quarter.

| Check                                                                | Action if failing                                        |
| -------------------------------------------------------------------- | -------------------------------------------------------- |
| CPU headroom < 30% over last 30 days                                 | Scale out; increase CPU limit                            |
| Memory headroom < 20% over last 30 days                              | Increase memory limit; investigate leaks                 |
| HPA triggered > 20 times in 30 days                                  | Raise min replicas baseline                              |
| P99 latency trending upward                                          | Profile request path; capacity may not be the root cause |
| Kafka consumer lag > 1 min at peak                                   | Add consumer replicas or partitions                      |
| Projected 6-month RPS exceeds current max replicas × 65% HPA trigger | Raise max replicas                                       |

Output: update the Capacity Worksheet (§4) and commit to `docs/sre/capacity-reviews/<service>-YYYY-QN.md`.
