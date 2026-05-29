# ADR-0007 — Service Mesh

**Status:** Accepted
**Date:** 2026-05-24
**Accepted:** 2026-05-29
**Authors:** Tech Lead, DevOps Lead
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
REM-003 (ISO 5.14/8.20, SOC 2 CC6.7) surfaces plaintext inter-service traffic as a
lateral-movement risk requiring a structured resolution.

---

## Options Evaluated

| Option          | mTLS   | Observability | Resource overhead  | Operational complexity  |
| --------------- | ------ | ------------- | ------------------ | ----------------------- |
| **Istio**       | ✅     | ✅ (Envoy)    | High (~200 MB/pod) | High (CRD surface area) |
| **Linkerd**     | ✅     | ✅ (native)   | Low (~10 MB/pod)   | Medium (simpler API)    |
| **Cilium mesh** | ✅     | ✅ (eBPF)     | Low (kernel-level) | Medium (eBPF expertise) |
| **No mesh**     | Manual | Manual        | None               | Low (current state)     |

---

## Decision

**Accepted: Istio.**

Istio is selected as the service mesh for this platform. Key rationale:

1. **Security team requirement** — Istio's `PeerAuthentication` CRD enforces STRICT mTLS
   across all pods via a single manifest, satisfying the zero-trust networking requirement
   that is mandatory before enterprise engagement (ISO 5.14/8.20, SOC 2 CC6.7).

2. **Observability depth** — Envoy's per-route L7 metrics (request rate, error rate, latency
   histograms) integrate directly with the existing Prometheus stack without application code
   changes, closing the network-layer observability gap noted in REM-003.

3. **Ecosystem maturity** — Istio has the largest production deployment base, the most
   comprehensive documentation, and the most active security advisory program. The higher
   operational complexity is acceptable given the SRE team's existing Kubernetes expertise.

4. **Linkerd was rejected** because its lightweight wire protocol is not yet FIPS-validated,
   which is a future requirement for regulated-data deployments. Cilium mesh was rejected
   due to the required eBPF kernel expertise not currently on the team.

---

## Implementation Phases

### Phase 1 — Template (this PR, REM-003 partial, 2026-05-29)

Deliverables that can be committed without a running cluster:

- Default-deny Kubernetes `NetworkPolicy` manifests (`infrastructure/k8s/network-policies/`)
- Documentation of the full Istio activation procedure

NetworkPolicies enforce pod-to-pod communication rules at the Kubernetes network layer
**before** Istio is installed. They remain in force with or without a mesh sidecar and
provide defence-in-depth when mTLS is not yet active.

### Phase 2 — Cluster activation (REM-003 full, requires real cluster)

Steps to activate when a managed Kubernetes cluster is provisioned:

```bash
# 1. Install Istio with minimal profile
istioctl install --set profile=minimal -y

# 2. Enable auto-injection in the target namespace
kubectl label namespace <namespace> istio-injection=enabled

# 3. Apply STRICT mTLS across the namespace
kubectl apply -f infrastructure/k8s/network-policies/istio-peer-auth.yaml

# 4. Apply all NetworkPolicy manifests
kubectl apply -f infrastructure/k8s/network-policies/

# 5. Verify mTLS: all traffic should show in Kiali with lock icons
istioctl x check-inject -n <namespace>
```

### Phase 3 — Observability integration (post-activation)

- Add Istio's Prometheus scrape job to `infrastructure/monitoring/prometheus/prometheus.yml`
- Import Istio Grafana dashboards alongside the existing golden-signals dashboard
- Wire `istio_requests_total` and `istio_request_duration_milliseconds` to SLO expressions

---

## Consequences

- **Phase 1 (done):** NetworkPolicy manifests enforce network-layer isolation at the
  Kubernetes CNI level. Inter-pod traffic is restricted to declared policies; all other
  traffic is denied by default. This is effective **without Istio** as long as the CNI
  plugin honours `NetworkPolicy` (Calico, Cilium, Weave — all do).

- **Phase 2 (pending cluster):** Istio sidecar injection adds ~200 MB memory and ~5 ms
  median latency per hop. Acceptable given the security posture improvement. Sidecar
  resource limits must be tuned per service in the Helm values files.

- **ADR-0003 (Async API):** Kafka traffic between pods is not covered by Istio (Kafka uses
  TCP, not HTTP). Kafka mTLS is configured separately via `KAFKA_SSL_*` broker settings.

---

## Alternatives Considered

**Linkerd** — rejected (not FIPS-validated wire protocol).

**Cilium mesh** — rejected (eBPF expertise gap on current team).

**Do nothing** — rejected (REM-003 is a P1 compliance gap blocking enterprise engagement).
