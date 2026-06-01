# Spec CAP-001: Capacity Planning Template

**Spec ID:** CAP-001
**Version:** 1.0.0
**Date:** 2026-05-31
**Status:** Accepted
**Author:** Valdomiro Souza

---

## 1. Problem Statement

The repository has no standard guidance for resource sizing, headroom planning,
or scaling decisions. Teams adopting this template must independently derive:

- CPU/memory/storage baselines per service type
- Headroom rules to prevent saturation under load spikes
- When to scale horizontally vs vertically
- How to set Kubernetes resource requests and limits
- Prerequisites before promoting a service to production capacity

## 2. Solution

Deliver `docs/sre/capacity-planning.md` — a capacity planning template with:

- Baseline resource sizing tables per language runtime
- Headroom rules with rationale
- K8s resource request/limit guidelines
- Horizontal vs vertical scaling decision matrix
- Load testing prerequisites
- Quarterly review template

## 3. Scope

### In scope

- Python (FastAPI), Java (Spring Boot), Go, Node.js/Next.js service types
- Kubernetes resource requests and limits
- Horizontal Pod Autoscaler (HPA) trigger thresholds
- Traffic growth projection formula
- Capacity review cadence

### Out of scope

- Cloud-provider-specific instance type recommendations
- Database capacity planning (handled by DBA team separately)
- Network bandwidth sizing

## 4. Acceptance Criteria

- [ ] `docs/sre/capacity-planning.md` present and follows repo doc style
- [ ] Sizing table covers all four language runtimes
- [ ] Headroom rules defined for CPU, memory, and disk
- [ ] K8s requests vs limits guidance present
- [ ] Scaling decision matrix covers ≥ 6 scenarios
- [ ] Load testing prerequisites listed
- [ ] Quarterly review template included
- [ ] CHANGELOG.md updated

## 5. References

- `docs/sre/slo/slo.yaml` — latency and availability targets inform sizing
- `docs/sre/deployment-strategy.md` — canary weights affect capacity headroom needed
- `infrastructure/helm/api-gateway/` — K8s resource definitions reference
