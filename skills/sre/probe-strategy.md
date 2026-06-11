# Skill: Kubernetes Probe Strategy

> **Activation:** Any Helm chart edit, new K8s Deployment, health endpoint change, or probe-related SLO work  
> **Spec:** specs/k8s/probe-strategy.md (K8S-001)  
> **ADR:** ADR-0042  
> **Runbook:** docs/sre/runbooks/RB-SRE-004-canary-probe-validation.md

---

## 1. Decision Tree — Which Probe for Which Check?

```
Is the check "is the process alive (not deadlocked/crashed)?"
  YES → livenessProbe  (and startupProbe with same path during boot)
  NO  ↓

Is the check "is the pod ready to receive traffic?"
  YES → readinessProbe
  NO  ↓

Is the check "has the container finished its slow boot sequence?"
  YES → startupProbe  (disables liveness + readiness until first success)
```

**Non-negotiable rules:**

- `livenessProbe` MUST NOT check external dependencies (DB, Redis, Kafka). If the DB is down, the pod should stay in Service and serve degraded responses — not restart.
- `readinessProbe` MAY check critical dependencies. Pod is removed from Service endpoints (no restart) on failure.
- `startupProbe` path = same as `livenessProbe`. It exists solely to extend the startup window without using `initialDelaySeconds`.
- **Never use `initialDelaySeconds` on `livenessProbe` or `readinessProbe`** — that is the anti-pattern that `startupProbe` replaces.

---

## 2. Endpoint Contract for This Repository

| Workload            | Liveness path                   | Readiness path                           | Health port |
| ------------------- | ------------------------------- | ---------------------------------------- | ----------- |
| Python API Gateway  | `GET /health` → 200 always      | `GET /ready` → 200/503 based on DB+Redis | 8000        |
| Java Domain Service | `GET /actuator/health/liveness` | `GET /actuator/health/readiness`         | 8080        |
| Go Event Worker     | `GET /healthz` → 200 always     | `GET /readyz` → 503 until Kafka join     | 8081        |

### Python `/health` invariant

`/health` MUST return `{"status":"ok"}` even when PostgreSQL, Redis, or Kafka are unreachable. If it checks dependencies, `startupProbe` will kill the pod during an infra blip — exactly the failure mode we are trying to prevent.

### Java Spring Boot requirement

`application.yml` MUST have:

```yaml
management:
  endpoint:
    health:
      probes:
        enabled: true
  health:
    livenessState:
      enabled: true
    readinessState:
      enabled: true
```

Without this, `/actuator/health/liveness` and `/actuator/health/readiness` return 404.

### Go worker readiness gate

`health.SetReady(true)` MUST only be called after `consumer.Run()` has confirmed Kafka partition assignment. Calling it before means the pod receives Kafka messages before it is ready to process them.

---

## 3. Parameter Tuning Guide

### Startup window sizing

```
startup window = failureThreshold × periodSeconds
```

| Workload         | Typical cold start              | Recommended window | Rationale                          |
| ---------------- | ------------------------------- | ------------------ | ---------------------------------- |
| Python gateway   | 5–30s (Alembic + Redis + flagd) | 150s (30×5)        | EKS cold node + migration lag      |
| Java Spring Boot | 15–90s (JVM JIT + Hibernate)    | 180s (36×5)        | JVM warmup on first request        |
| Go event-worker  | 1–10s                           | 60s (12×5)         | Kafka group coordinator round-trip |

**Tuning rule:** if pods are restarting with `Liveness probe failed` in events during deploy, the startup window is too small. Increase `failureThreshold` first (not `periodSeconds`) to keep probe responsiveness high after startup completes.

### terminationGracePeriodSeconds

Must exceed the longest in-flight request at shutdown:

| Workload            | Value | Rationale                                       |
| ------------------- | ----- | ----------------------------------------------- |
| Python gateway      | 60s   | Longest HITL decision polling window (ADR-0011) |
| Java domain service | 90s   | JVM shutdown sequence + Kafka offset commit     |
| Go event-worker     | 30s   | preStop sleep (15s) + message drain             |

The `preStop: exec: sleep N` hook = `terminationGracePeriodSeconds / 2`. This gives the load balancer time to drain connections before SIGTERM fires.

### timeoutSeconds

Never leave at the default of 1s for HTTP probes on production workloads. Under CPU pressure, even `/health` can take >1s.

Minimums: Python/Java = 5s liveness, 3s startup. Go = 3s liveness, 2s startup.

---

## 4. Values-Driven Template Checklist

Every `values.yaml` MUST have all three probe sections:

```yaml
probes:
  startup:
    path: /health # workload-specific
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

Every `templates/deployment.yaml` MUST:

- Reference `{{ .Values.probes.startup.* }}` — no hardcoded probe values
- Have NO `initialDelaySeconds` on liveness or readiness
- Use the correct named port reference (`port: http`, `port: health`, etc.)

---

## 5. Testing Probes Locally

```bash
# Start the full dev stack
make infra-up && make run

# Test liveness — must return 200 even with no DB
curl -sv http://localhost:8000/health

# Test readiness — must return 503 when DB/Redis is not up
make infra-down
curl -sv http://localhost:8000/ready   # expect 503

# Simulate startup probe manually
for i in $(seq 1 5); do
  curl -sw "attempt $i → %{http_code}\n" -o /dev/null http://localhost:8000/health
  sleep 5
done

# Go event-worker health server (port 8081)
curl -sv http://localhost:8081/healthz   # always 200
curl -sv http://localhost:8081/readyz    # 503 until Kafka joined

# Java Spring Boot actuator probes
curl -sv http://localhost:8080/actuator/health/liveness
curl -sv http://localhost:8080/actuator/health/readiness
```

---

## 6. CI Lint Gate

The `ci-k8s-probe-lint.yml` workflow validates all manifests under `infrastructure/` on every PR that touches that path. It checks:

1. **kubeconform** — all YAML is valid against the Kubernetes API schema
2. **Probe completeness** — every Deployment must have `startupProbe`, `livenessProbe`, and `readinessProbe`
3. **terminationGracePeriodSeconds** — must be set on every Deployment

A PR annotation is emitted for each missing item. Currently informational; becomes blocking once all workloads are confirmed compliant.

---

## 7. When to Escalate

Emit `[HITL-ESCALATE]` if:

- Removing a probe (any type) from a production workload
- Changing `terminationGracePeriodSeconds` to a value lower than the HITL SLA (ADR-0011: 60s for Python gateway)
- Disabling `livenessProbe` on any workload (masks crashed pods from the scheduler)
