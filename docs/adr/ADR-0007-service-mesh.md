# ADR-0007 — Service Mesh

**Status:** Proposed
**Date:** 2026-05-24
**Authors:** Tech Lead, DevOps Lead
**Decision target:** 2026-08-01
**Owner:** DevOps Lead

---

## Context

As the number of inter-service calls grows (API Gateway → Agent Service → HITL Gateway),
the following cross-cutting concerns need a consistent implementation:

- Mutual TLS (mTLS) for all service-to-service traffic
- Automatic retries and circuit breaking at the network layer
- Fine-grained traffic observability (per-route latency, error rate) without modifying application code
- Zero-trust networking: no service trusts another by identity alone

Currently these concerns are handled ad-hoc at the application layer (httpx retry config,
manual TLS certificate management). This approach does not scale as services multiply.

---

## Options Under Evaluation

| Option          | mTLS   | Observability | Resource overhead  | Operational complexity  |
| --------------- | ------ | ------------- | ------------------ | ----------------------- |
| **Istio**       | ✅     | ✅ (Envoy)    | High (~200 MB/pod) | High (CRD surface area) |
| **Linkerd**     | ✅     | ✅ (native)   | Low (~10 MB/pod)   | Medium (simpler API)    |
| **Cilium mesh** | ✅     | ✅ (eBPF)     | Low (kernel-level) | Medium (eBPF expertise) |
| **No mesh**     | Manual | Manual        | None               | Low (current state)     |

---

## Decision

**Pending.** Decision will be made by 2026-08-01 after:

1. PoC of Linkerd on the staging cluster measuring latency overhead and mTLS setup time
2. Security team review of certificate rotation strategy for each option
3. SRE team assessment of operational runbook burden per option

Until this ADR is accepted, inter-service mTLS is implemented manually via client certificate
configuration in each service. This is tracked as a known gap in the PRR checklist
(`docs/sre/prr/prr-checklist.yaml`).

---

## Consequences of Deferral

- Manual mTLS certificate rotation is error-prone and must be monitored via the
  `CertificateExpiryWarning` alert (to be added to `golden-signals.yaml`).
- Inter-service observability is limited to application-level OTel spans until a mesh sidecar
  provides network-level metrics.

---

## Alternatives Considered

**Do nothing (current state)**
Acceptable short-term. Becomes a compliance risk if zero-trust networking is required
before 2026-08-01 by the security team's roadmap.

**Consul Connect**
Lower priority for PoC — requires Consul installation; adds another control plane
to operate alongside Kubernetes.
