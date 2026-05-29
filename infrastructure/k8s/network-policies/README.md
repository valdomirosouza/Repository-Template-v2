# Kubernetes NetworkPolicy Manifests

ADR: [ADR-0007 — Service Mesh (Accepted: Istio)](../../../docs/adr/ADR-0007-service-mesh.md)
REM: REM-003 (ISO 5.14/8.20, SOC 2 CC6.7)

## Overview

These manifests implement network-layer isolation for all services in the deployment namespace.
They enforce the **default-deny** model: all ingress is blocked unless explicitly permitted by a
policy in this directory.

## Files

| File                        | Purpose                                                                     |
| --------------------------- | --------------------------------------------------------------------------- |
| `default-deny-ingress.yaml` | Blocks all inbound traffic to every pod; other policies open specific ports |
| `api-gateway.yaml`          | api-gateway, event-worker, domain-service ingress/egress rules              |
| `monitoring.yaml`           | Allows Prometheus scraping; Alertmanager egress to PagerDuty/Slack          |
| `istio-peer-auth.yaml`      | **Phase 2 only** — Istio STRICT mTLS across the namespace                   |

## Two-Phase Activation

### Phase 1 — NetworkPolicies (no Istio required)

Apply the CNI-level policies to any cluster that supports `NetworkPolicy`:

```bash
# Apply all policies except the Istio-specific PeerAuthentication
kubectl apply -f infrastructure/k8s/network-policies/default-deny-ingress.yaml
kubectl apply -f infrastructure/k8s/network-policies/api-gateway.yaml
kubectl apply -f infrastructure/k8s/network-policies/monitoring.yaml

# Verify: all pods should still be reachable on their declared ports
kubectl get networkpolicy -n <namespace>
```

NetworkPolicies are enforced by the CNI plugin (Calico, Cilium, Weave) regardless of whether
Istio is installed. They remain the primary isolation layer.

### Phase 2 — Istio mTLS (requires cluster + Istio installation)

```bash
# 1. Install Istio (minimal profile)
istioctl install --set profile=minimal -y

# 2. Enable sidecar injection for your namespace
kubectl label namespace <namespace> istio-injection=enabled

# 3. Apply STRICT mTLS — rejects all non-mTLS pod-to-pod traffic
kubectl apply -f infrastructure/k8s/network-policies/istio-peer-auth.yaml

# 4. Restart pods to inject sidecars
kubectl rollout restart deployment -n <namespace>

# 5. Verify
istioctl x check-inject -n <namespace>
```

## Customisation

- **Namespace**: change `namespace: default` in each manifest to match your deployment namespace.
- **Label selectors**: manifests use `app: <service-name>` labels matching the Helm chart defaults.
  If your Helm values override these labels, update the `matchLabels` blocks accordingly.
- **Kafka mTLS**: Kafka traffic is TCP (not HTTP) and is not covered by Istio sidecar mTLS.
  Configure `KAFKA_SSL_*` broker settings separately per ADR-0005.
