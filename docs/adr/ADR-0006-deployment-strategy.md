# ADR-0006 — Deployment Strategy

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead, DevOps Lead, SRE Lead

---

## Context

The system must support:

- Zero-downtime deployments (SLO target: ≥ 99.9% availability)
- Progressive traffic shifting to detect regressions before full rollout
- Fast, reliable rollback when a Golden Signal breach is detected
- Multi-environment promotion: dev → staging → production
- Audit trail for every production deployment (compliance requirement)

---

## Decision

Adopt **Kubernetes + Helm** as the deployment platform with a **canary-first** strategy
for production and **blue-green** as the fallback for high-risk releases.

### Canary deploy (default for production)

```
5% traffic → wait 15 min → check Golden Signals
  └── pass → 25% → wait 15 min → check Golden Signals
        └── pass → 100%
              └── fail at any gate → auto-rollback to previous revision
```

Gates at each step:

- Error rate < 1% over the 15-minute window
- p99 latency < 500ms
- No `CriticalErrorRate` or `CriticalP99Latency` Prometheus alerts firing

### Blue-green (for schema migrations or breaking changes)

1. Deploy green (new version) alongside blue (current version)
2. Run smoke tests against green
3. Switch load balancer to green
4. Keep blue alive for 30 minutes (immediate rollback window)
5. Tear down blue after confirmation

Implementation:

- `infrastructure/scripts/deploy/deploy.sh` — canary and blue-green logic
- `infrastructure/scripts/deploy/smoke-test.sh` — post-deploy health verification
- `infrastructure/scripts/deploy/rollback.sh` — rollback to previous Helm revision
- `.github/workflows/cd-production.yml` — CI/CD pipeline with gate enforcement

---

## Consequences

### Positive

- Canary strategy detects regressions affecting a small percentage of real traffic
  before they reach 100% — reduces blast radius of bad deployments.
- Helm revision history enables `helm rollback` to any previous release with a single command.
- Golden Signal gates are automated — no manual approval needed for standard deploys.
- The same Helm chart deploys to all environments; only `values-<env>.yaml` differs.

### Negative / Trade-offs

- Canary requires the application to be stateless or backward-compatible across versions
  during the traffic-split window.
- Blue-green doubles resource consumption during the overlap window.
- Kubernetes operational overhead: cluster management, HPA tuning, PDB configuration.

---

## Alternatives Considered

**Heroku / Railway / Render (PaaS)**
Rejected: insufficient control over networking, resource limits, and Kafka broker co-location;
PaaS pricing at scale exceeds self-hosted Kubernetes cost.

**ECS + ALB weighted target groups**
Rejected: AWS-specific; lock-in inconsistent with multi-cloud posture; Helm portability
preferred for reproducibility across cloud providers.

**Rolling deployment only**
Rejected: rolling updates expose all traffic to the new version without a controlled
ramp-up window; incompatible with the 99.9% availability SLO for high-risk releases.
