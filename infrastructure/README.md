# infrastructure/

Infrastructure-as-Code (IaC) and platform configuration for the enterprise AI monorepo.

---

## Directory Map

| Directory         | Purpose                                                                  |
| ----------------- | ------------------------------------------------------------------------ |
| `k8s/`            | Kubernetes manifests — Deployment, Service, HPA, PDB, Prometheus Adapter |
| `helm/`           | Helm charts for service deployment (canary / rolling / blue-green)       |
| `terraform/`      | Terraform modules for cloud infrastructure (K8s, Kafka, Redis, DB)       |
| `monitoring/`     | Prometheus rules, Grafana dashboards, OTel Collector, Jaeger config      |
| `feature-flags/`  | OpenFeature flagd deployment + flag YAML definitions                     |
| `message-broker/` | Kafka topic definitions and Avro schema registry                         |
| `scripts/`        | Deploy, rollback, smoke-test, and DB migration shell scripts             |

---

## Key Files

### Kubernetes (`k8s/`)

| File                             | Description                                                                                                          |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `deployment.yaml`                | Agent-service Deployment — startupProbe, livenessProbe, readinessProbe, preStop drain, resource limits, secretKeyRef |
| `service.yaml`                   | ClusterIP Service for agent-service                                                                                  |
| `hpa.yaml`                       | HorizontalPodAutoscaler — CPU (70%) + `agent_semaphore_waiting` (avg > 3) + `kafka_consumer_lag` (> 5000)            |
| `pdb.yaml`                       | PodDisruptionBudget — `minAvailable: 2` (PRR-CAP-003)                                                                |
| `prometheus-adapter-config.yaml` | ConfigMap mapping Prometheus metrics to `custom.metrics.k8s.io` for HPA                                              |

### Monitoring (`monitoring/`)

| File                                                          | Description                                                               |
| ------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `prometheus/rules/golden-signals.yaml`                        | PrometheusRule: traffic, error rate, saturation alerts with `runbook_url` |
| `grafana/dashboards/golden-signals.json`                      | Grafana dashboard — Golden Signals overview                               |
| `grafana/dashboards/sre-overview.json`                        | Grafana dashboard — SLO + Error Budget                                    |
| `grafana/cuj-dashboards/CUJ-001-user-request-processing.json` | CUJ-001 dashboard (PRR-OBS-005) — 12 panels covering all 7 CUJ steps      |

### Feature Flags (`feature-flags/`)

See [`feature-flags/README.md`](feature-flags/README.md) for full details.

| File                         | Description                                                         |
| ---------------------------- | ------------------------------------------------------------------- |
| `flagd.yaml`                 | K8s Deployment + Service + ConfigMap for flagd (OpenFeature server) |
| `flags/autonomous-mode.yaml` | `autonomous-mode` flag — controls HITL/HOTL mode (default: `off`)   |

---

## Probe Configuration (deployment.yaml)

The Deployment uses all three Kubernetes probe types:

```
startupProbe  → failureThreshold: 30 × periodSeconds: 10 = 5-min startup window
                Prevents premature liveness kills during slow boot (asyncpg pool + Redis ping)

livenessProbe → httpGet /health (no dep checks — fast, no false positives)
                initialDelaySeconds: 5 (startupProbe owns the startup gate)

readinessProbe → httpGet /ready (checks DB SELECT 1 + Redis PING, both with 2s timeout)
                 Returns 503 when a dependency is unreachable — pod removed from Service endpoints
```

---

## HPA Custom Metrics

The HPA scales on three signals (requires Prometheus Adapter):

| Metric                    | Type     | Scale threshold           | Source                         |
| ------------------------- | -------- | ------------------------- | ------------------------------ |
| CPU                       | Resource | > 70% average utilization | kube-metrics-server            |
| `agent_semaphore_waiting` | Pods     | avg > 3 per pod           | `src/observability/metrics.py` |
| `kafka_consumer_lag`      | Object   | > 5000 messages           | `src/observability/metrics.py` |

Mapping rules: `k8s/prometheus-adapter-config.yaml`

---

## Deployment Strategy

Rolling update with zero downtime:

```yaml
rollingUpdate:
  maxSurge: 1 # One extra pod during update
  maxUnavailable: 0 # No pod removed until replacement is ready
```

Scale-down stabilization: 300s (prevents flapping on traffic bursts).

---

## Related ADRs

- [ADR-0005](../docs/adr/ADR-0005-message-broker-selection.md) — Deployment strategy
- [ADR-0006](../docs/adr/ADR-0006-deployment-strategy.md) — Canary + Blue-Green
- [ADR-0008](../docs/adr/ADR-0008-secrets-management.md) — Secrets via secretKeyRef
- [ADR-0015](../docs/adr/ADR-0015-feature-flag-strategy.md) — Feature flag strategy (flagd + OpenFeature)
