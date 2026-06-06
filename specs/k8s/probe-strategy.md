# Spec: Kubernetes Probe Strategy

> **Spec ID:** K8S-001  
> **Status:** Approved  
> **Version:** 1.0.0  
> **Date:** 2026-06-05  
> **Author:** Platform Team  
> **ADR:** ADR-0042  
> **Issue:** #20, #21, #22, #23, #24  
> **Reference:** k8s-probes-compliance-v2.md

---

## 1. Purpose

Define the authoritative probe configuration contract for every workload in this monorepo. All Kubernetes Deployment manifests (Helm and static) MUST conform to this spec before production deployment.

---

## 2. Probe Roles (non-negotiable)

| Probe            | Fires                      | On Failure                    | Endpoint contract            |
| ---------------- | -------------------------- | ----------------------------- | ---------------------------- |
| `startupProbe`   | Once, at container boot    | Kill + restart                | Process-alive only — no deps |
| `livenessProbe`  | Continuously after startup | Kill + restart                | Process-alive only — no deps |
| `readinessProbe` | Continuously after startup | Remove from Service endpoints | May check critical deps      |

**Rule:** `livenessProbe` and `readinessProbe` MUST NOT share the same path as the `startupProbe` check if that check includes dependency health — liveness must never fail due to a downstream dependency blip.

---

## 3. Endpoint Contract Per Workload

### 3.1 Python API Gateway (FastAPI)

| Path          | Port | Checks             | Returns                                |
| ------------- | ---- | ------------------ | -------------------------------------- |
| `GET /health` | 8000 | Process alive      | `200 {"status":"ok"}` always           |
| `GET /ready`  | 8000 | PostgreSQL + Redis | `200` when all up; `503` when any down |

`/health` MUST return `200` even when PostgreSQL or Redis are unreachable.

### 3.2 Java Domain Service (Spring Boot)

| Path                             | Port | Checks                            | Returns       |
| -------------------------------- | ---- | --------------------------------- | ------------- |
| `GET /actuator/health/liveness`  | 8080 | Spring HealthIndicator (JVM only) | `200` / `503` |
| `GET /actuator/health/readiness` | 8080 | DataSource + Kafka                | `200` / `503` |

Spring Boot `management.endpoint.health.probes.enabled: true` MUST be set.

### 3.3 Go Event Worker

| Path           | Port | Checks                      | Returns                        |
| -------------- | ---- | --------------------------- | ------------------------------ |
| `GET /healthz` | 8081 | Process alive               | `200` always                   |
| `GET /readyz`  | 8081 | Kafka consumer group joined | `200` after join; `503` before |

The health server runs on port 8081 (separate from metrics on 8080/9091).  
`ready` state MUST be set to `true` only after `consumer.Run()` completes its Kafka group join.

---

## 4. Parameter Reference Table

| Field                               | Python Gateway                    | Java Domain Service          | Go Event Worker |
| ----------------------------------- | --------------------------------- | ---------------------------- | --------------- |
| `startupProbe.failureThreshold`     | 30                                | 36                           | 12              |
| `startupProbe.periodSeconds`        | 5                                 | 5                            | 5               |
| `startupProbe.timeoutSeconds`       | 3                                 | 3                            | 2               |
| `startupProbe.path`                 | `/health`                         | `/actuator/health/liveness`  | `/healthz`      |
| `livenessProbe.path`                | `/health`                         | `/actuator/health/liveness`  | `/healthz`      |
| `livenessProbe.periodSeconds`       | 15                                | 20                           | 15              |
| `livenessProbe.timeoutSeconds`      | 5                                 | 5                            | 3               |
| `livenessProbe.failureThreshold`    | 3                                 | 3                            | 3               |
| `livenessProbe.initialDelaySeconds` | **0** (startupProbe handles this) | **0**                        | **0**           |
| `readinessProbe.path`               | `/ready`                          | `/actuator/health/readiness` | `/readyz`       |
| `readinessProbe.periodSeconds`      | 10                                | 10                           | 10              |
| `readinessProbe.timeoutSeconds`     | 5                                 | 5                            | 3               |
| `readinessProbe.failureThreshold`   | 3                                 | 3                            | 3               |
| `terminationGracePeriodSeconds`     | **60**                            | **90**                       | 30              |

`terminationGracePeriodSeconds` rationale:

- Python Gateway: 60s — must exceed longest HITL in-flight request (ADR-0011 SLA)
- Java Domain Service: 90s — JVM shutdown + in-flight Kafka message processing
- Go Event Worker: 30s — fast shutdown; preStop sleep = 15s (half of 30s)

---

## 5. Values-Driven Templating Rule

All probe parameters MUST be defined in `values.yaml` under `probes.startup`, `probes.liveness`, and `probes.readiness`. No probe parameters may be hardcoded in `templates/deployment.yaml`.

```yaml
# Canonical values.yaml probe structure (all three probes required)
probes:
  startup:
    path: /health # or /healthz, /actuator/health/liveness
    failureThreshold: 30
    periodSeconds: 5
    timeoutSeconds: 3
  liveness:
    path: /health
    periodSeconds: 15
    timeoutSeconds: 5
    failureThreshold: 3
  readiness:
    path: /ready
    periodSeconds: 10
    timeoutSeconds: 5
    failureThreshold: 3
terminationGracePeriodSeconds: 60
```

---

## 6. Canary Promotion Gate

Before each canary traffic promotion (5%→25%, 25%→100%), the CD pipeline MUST:

1. Run `kubectl rollout status deployment/<name>-canary --timeout=120s`
2. Assert zero pods with `Ready=False` in the canary pod selector
3. Abort promotion if either check fails

---

## 7. CI Probe Completeness Gate

The `ci-k8s-probe-lint.yml` workflow validates:

- All rendered Helm templates contain `livenessProbe`, `readinessProbe`, `startupProbe`
- All Deployment manifests in `infrastructure/k8s/` contain all three probe types
- `terminationGracePeriodSeconds` is set on every Deployment

Initially informational (PR annotation); becomes blocking after all workloads are compliant.
