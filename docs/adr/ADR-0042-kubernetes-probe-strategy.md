# ADR-0042 — Kubernetes Probe Strategy

| Field          | Value                                                   |
| -------------- | ------------------------------------------------------- |
| **Status**     | Accepted                                                |
| **Date**       | 2026-06-05                                              |
| **Deciders**   | Platform Team, SRE Lead                                 |
| **Spec**       | specs/k8s/probe-strategy.md (K8S-001)                   |
| **Issues**     | #20, #21, #22, #23, #24                                 |
| **Supersedes** | —                                                       |
| **Related**    | ADR-0011 (HITL/HOTL model), ADR-0002 (Technology Stack) |

---

## Context

The repository ships Kubernetes manifests for three workloads — Python FastAPI gateway, Java Spring Boot domain-service, and Go event-worker. A compliance audit against the Kubernetes probe documentation (`k8s-probes-compliance-v2.md`) identified these gaps:

- **GO-1/GO-2** — Go event-worker had no dedicated health endpoints serving `/healthz`/`/readyz`; the Helm chart referenced these paths but main.go only served `/health` on the metrics port. No `startupProbe` present.
- **PY-3/PY-4/PY-5** — Python gateway used `initialDelaySeconds` as a proxy for missing `startupProbe` parameters in `values.yaml`. `terminationGracePeriodSeconds` was 30s, shorter than the maximum HITL in-flight request window.
- **JAVA-2** — Spring Boot's native liveness/readiness probe groups were not activated (`management.endpoint.health.probes.enabled` absent), meaning `/actuator/health/liveness` and `/actuator/health/readiness` returned 404.
- **HELM-1** — Startup probe parameters were hardcoded in Helm templates, not driven from `values.yaml`.
- **CD-1** — The canary CD pipeline promoted traffic (5%→25%, 25%→100%) without verifying that readiness probes were stable on the current pods.

---

## Decision

### 1. Probe role separation is absolute

- `startupProbe` and `livenessProbe` MUST point to a path that checks process health only — no external dependencies.
- `readinessProbe` MAY check critical dependencies (DB, Redis, Kafka). Pod removal from Service endpoints on failure is the correct K8s signal; it does not trigger a restart.
- `initialDelaySeconds` on `livenessProbe` or `readinessProbe` is prohibited. `startupProbe` provides the correct mechanism.

### 2. Dedicated health port for Go services

The Go event-worker runs a dedicated HTTP server on port 8081 (`internal/health/server.go`) with an `atomic.Bool` ready flag. This is isolated from the Prometheus metrics port (9091) so probe traffic does not interfere with metrics scraping. `SetReady(true)` is called only after the Kafka consumer group has completed partition assignment.

### 3. Spring Boot probe groups mandatory

All Spring Boot services MUST enable:

```yaml
management.endpoint.health.probes.enabled: true
management.health.livenessState.enabled: true
management.health.readinessState.enabled: true
```

This activates the `/actuator/health/liveness` and `/actuator/health/readiness` sub-paths, which are aligned precisely to the K8s probe model and managed by Spring's internal `ApplicationAvailability` state machine.

### 4. Values-driven probe configuration

All probe parameters (`failureThreshold`, `periodSeconds`, `timeoutSeconds`, path) MUST be defined in `values.yaml` under `probes.startup`, `probes.liveness`, `probes.readiness`. No probe parameter may be hardcoded in `templates/deployment.yaml`. This enables per-environment tuning without template changes.

### 5. terminationGracePeriodSeconds aligned to workload SLAs

| Workload            | Value | Rationale                                       |
| ------------------- | ----- | ----------------------------------------------- |
| Python gateway      | 60s   | Longest HITL decision polling window (ADR-0011) |
| Java domain-service | 90s   | JVM shutdown + Kafka offset commit drain        |
| Go event-worker     | 30s   | Fast shutdown; preStop sleep = 15s              |

### 6. Canary promotion gates

The CD pipeline (`cd-production.yml`) MUST run `kubectl rollout status` and assert zero `Ready=False` pods before each traffic promotion step (5%→25% and 25%→100%). This catches readiness probe flapping that would pass the Golden Signals gate if the unready pods are not yet receiving traffic.

---

## Consequences

**Positive:**

- Eliminates unnecessary pod restart cascades during EKS cold-node starts (startup window sized to workload profile).
- Prevents traffic loss from conflating dependency health with pod liveness.
- Canary promotions are gated on actual readiness probe stability, not just error-rate metrics.
- All probe parameters are tunable per environment without template changes.

**Negative:**

- Go event-worker now maintains an additional HTTP server goroutine. Overhead is negligible (<1MB RAM, <0.1% CPU).
- The Java domain-service requires `spring-boot-actuator` on the classpath — already a dependency for Prometheus metrics.
- `terminationGracePeriodSeconds: 90` on the Java domain-service means rolling deploys take up to 90s per pod for graceful shutdown.

---

## Compliance Notes

- All probe changes require the `ci-k8s-probe-lint.yml` gate to pass (kubeconform + probe completeness check).
- Reducing `terminationGracePeriodSeconds` below the values in §5 requires HITL escalation (ADR-0011 SLA impact).
- Removing any probe type from a production workload requires dual-approval from SRE Lead + Platform Team.
