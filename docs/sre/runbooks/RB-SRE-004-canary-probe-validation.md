# RB-SRE-004 — Canary Probe Validation & Rollback

> **Spec:** specs/k8s/probe-strategy.md §6  
> **ADR:** ADR-0042  
> **Issue:** #23  
> **Severity:** P1 — blocks canary promotion

---

## When This Runbook Applies

The `cd-production.yml` workflow fails at either of these gates:

- **"Verify canary readiness stability before 5%→25% promotion"**
- **"Verify canary readiness stability before 25%→100% promotion"**

The gate aborts the canary if any pod in the `api-gateway` selector reports `Ready=False` after `kubectl rollout status` completes.

---

## 1. Diagnose — Inspect Probe Failures

```bash
# Which pods are unready?
kubectl get pods -n production \
  --selector=app.kubernetes.io/name=api-gateway \
  -o wide

# Full probe event history for a failing pod
kubectl describe pod <pod-name> -n production | grep -A 20 "Events:"

# Recent probe logs from the container
kubectl logs <pod-name> -n production --tail=100

# Check readiness probe endpoint directly
kubectl port-forward pod/<pod-name> 8000:8000 -n production &
curl -v http://localhost:8000/ready
curl -v http://localhost:8000/health
```

### Common root causes

| Symptom                   | Likely cause                                                                                     |
| ------------------------- | ------------------------------------------------------------------------------------------------ |
| `/ready` returns 503      | DB or Redis connection pool exhausted — check `db_pool` / `redis` in logs                        |
| `/ready` returns 500      | Unhandled exception in health router — should return 503; check `src/api/rest/routers/health.py` |
| `/health` returns non-200 | Process crashed or deadlocked — check OOM events, restart count                                  |
| Probe timeout (>5s)       | High CPU load on pod; check HPA, increase `timeoutSeconds` in values                             |
| startupProbe failure      | Container still initialising; check Alembic migration or flagd handshake in startup logs         |

---

## 2. Rollback

If probes are flapping and the cause cannot be resolved quickly, roll back the canary:

```bash
# Rollback to stable image (removes canary)
make rollback

# Or manually via Helm
helm rollback app -n production

# Verify rollback completed
kubectl rollout status deployment/app-api-gateway -n production --timeout=120s
kubectl get pods -n production --selector=app.kubernetes.io/name=api-gateway
```

Rollback must complete within `dora_mttr_target_seconds: 3600` per `docs/sre/slo/slo.yaml`.

---

## 3. Investigate Probe Parameters

If the probe gate fires due to slow startup (e.g., cold node), verify the startup window is sufficient:

```bash
# Check startup probe configuration
kubectl get deployment app-api-gateway -n production \
  -o jsonpath='{.spec.template.spec.containers[0].startupProbe}' | jq .

# Current window = failureThreshold × periodSeconds
# Python gateway: 30 × 5 = 150s
# Java domain service: 36 × 5 = 180s
# Go event-worker: 12 × 5 = 60s
```

To temporarily increase the startup window without redeploying:

```bash
kubectl patch deployment app-api-gateway -n production \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/failureThreshold","value":45}]'
```

Then update `infrastructure/helm/api-gateway/values.yaml` `probes.startup.failureThreshold` before the next deploy.

---

## 4. Re-trigger Canary Promotion

After fixing the root cause:

1. Confirm all pods are Ready: `kubectl get pods -n production -l app.kubernetes.io/name=api-gateway`
2. Re-run the failed CD workflow from GitHub Actions → **cd-production** → **Re-run failed jobs**
3. Monitor Golden Signals for 15 minutes before the next promotion step

---

## 5. Post-Incident

- Open a GitHub Issue tagged `k8s-probe` describing the failure mode
- If `timeoutSeconds` was too low, update `specs/k8s/probe-strategy.md` §4 with revised values
- If the `/ready` endpoint returned 500 instead of 503, fix `src/api/rest/routers/health.py` to return `HTTPException(503)` for all dependency failures
