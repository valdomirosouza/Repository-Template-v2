# Runbook: Redis Connection Failure

**Owner:** SRE Lead | **Reviewer:** Security Lead | **Last updated:** 2026-05-28
**Alert:** `RedisConnectionFailure` (connection errors > 0 for 2 min)
**SLO reference:** `docs/sre/slo/slo.yaml` → `api-gateway.availability`
**Dashboard:** `infrastructure/monitoring/grafana/dashboards/golden-signals.json`
**Security note:** Production Redis requires TLS (`rediss://`) and value-level encryption (ADR-0019). Any fallback that bypasses these is a security violation.

---

## Critical Safety Rules

> **Production only — in-memory fallback is BLOCKED.**
> `InMemoryHITLStore` and `InMemoryRequestStore` activate automatically in local dev, but are rejected when `app_env=production` (`Settings.reject_placeholder_secrets`). A Redis failure in production means:
>
> - All new HITL requests cannot be persisted → agent pipeline stalls
> - All new domain requests cannot be queued → users see 503
> - Existing in-flight requests are not lost (already in PostgreSQL audit log)

---

## Step 1 — Assess (< 3 minutes)

```bash
# Check Redis pod health
kubectl get pods -n redis -l app=redis
kubectl describe pod -n redis -l app=redis | grep -E "Status|Reason|Exit"

# Check connection errors in app logs
kubectl logs -n default -l app=api-gateway --tail=100 --since=3m | \
  grep -i "redis\|connection\|refused\|timeout"

# Check TLS connectivity (production uses rediss://)
kubectl exec -n default deploy/api-gateway -- \
  python3 -c "
import redis, os
r = redis.Redis.from_url(os.environ.get('REDIS_URL','redis://localhost:6379'))
print(r.ping())
" 2>&1

# Check if TLS is required but missing
kubectl logs -n default -l app=api-gateway --tail=50 | grep -i "ssl\|tls\|certificate"
```

---

## Step 2 — Identify Root Cause

### 2a. Redis pod down or restarting

```bash
# Check restart count and recent events
kubectl describe pod -n redis -l app=redis | grep -A 10 "Events:"
kubectl get events -n redis --sort-by='.lastTimestamp' | tail -20

# Check PersistentVolume health
kubectl get pvc -n redis
kubectl describe pvc -n redis | grep -E "Status|Capacity|Access"
```

### 2b. Network policy blocking connection

```bash
# List NetworkPolicies in the default namespace
kubectl get networkpolicies -n default
kubectl describe networkpolicies -n default | grep -A 10 "Egress"

# Test direct TCP connectivity from app pod
kubectl exec -n default deploy/api-gateway -- \
  nc -zv redis-service 6380 2>&1  # 6380 for TLS
```

### 2c. TLS certificate expired

```bash
# Check Redis TLS certificate expiry
kubectl exec -n redis deploy/redis -- \
  openssl s_client -connect localhost:6380 </dev/null 2>&1 | \
  openssl x509 -noout -dates 2>/dev/null
```

### 2d. Memory pressure / OOM

```bash
# Redis memory usage
kubectl exec -n redis deploy/redis -- redis-cli INFO memory | \
  grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio"

# Check if evictions are occurring
kubectl exec -n redis deploy/redis -- redis-cli INFO stats | \
  grep evicted_keys
```

### 2e. Auth failure (key rotation side effect)

```bash
# Check for AUTH errors in logs
kubectl logs -n default -l app=api-gateway --tail=100 | grep -i "auth\|password\|wrong"

# Verify REDIS_URL secret is current
kubectl get secret redis-credentials -n default -o jsonpath='{.data.url}' | \
  base64 -d | sed 's/:\/\/.*@/:\\/\\/<redacted>@/'
```

---

## Step 3 — Remediation

### 3a. Redis pod restart

```bash
kubectl rollout restart deployment/redis -n redis
kubectl rollout status deployment/redis -n redis --timeout=120s

# Wait for readiness probe to pass, then confirm app reconnects
sleep 15
kubectl logs -n default -l app=api-gateway --tail=20 | \
  grep -i "redis\|connected\|ready"
```

### 3b. Restore from PVC (data recovery)

If the Redis pod is gone but the PVC is healthy, data will auto-recover on pod restart — Redis persists HITL state to the PVC (RDB snapshots + AOF). Confirm:

```bash
kubectl exec -n redis deploy/redis -- redis-cli DBSIZE
kubectl exec -n redis deploy/redis -- redis-cli INFO persistence | \
  grep -E "rdb_last_bgsave_status|aof_enabled|aof_last_write_status"
```

### 3c. Data-loss scenario — recovery from audit log

If Redis PVC data is lost (pod + PVC deleted):

- **HITL state loss:** In-flight HITL requests are lost. Reconstruct from the PostgreSQL audit log (INSERT-only, never deleted).
- **Request state loss:** In-flight domain requests are lost. Affected users must resubmit.

```bash
# Identify in-flight requests from audit log
psql $DATABASE_URL -c "
  SELECT correlation_id, action, outcome, occurred_at
  FROM audit_events
  WHERE outcome = 'pending_hitl'
  ORDER BY occurred_at DESC
  LIMIT 20;"
```

Notify affected users and the AI Governance Lead of any HITL state loss.

### 3d. Fix network policy blocking

```bash
# Temporarily open Redis egress for diagnosis
kubectl patch networkpolicy api-gateway-egress -n default \
  --type='json' \
  -p='[{"op":"add","path":"/spec/egress/-","value":{"ports":[{"port":6380,"protocol":"TCP"}]}}]'
```

File an RFC to make the policy change permanent via the normal change process.

### 3e. TLS certificate renewal

If the Redis TLS certificate has expired, follow `docs/sre/runbooks/cert-rotation.md` for certificate rotation.

---

## Step 4 — Data-Loss Communication Protocol

Any Redis failure that results in lost HITL or request state requires:

1. **Immediately:** Notify AI Governance Lead of HITL state loss.
2. **Within 1 hour:** Audit log reconstruction (Step 3c above).
3. **Within 2 hours:** Notify affected users that their requests need resubmission.
4. **Within 48 hours:** Postmortem in `docs/postmortems/`.
5. **GDPR/LGPD check:** If lost state included unmasked personal data — notify DPO within 72 hours.

---

## Step 5 — Verify Recovery

```bash
# Redis responds to PING
kubectl exec -n default deploy/api-gateway -- \
  python3 -c "import redis, os; print(redis.Redis.from_url(os.environ.get('REDIS_URL')).ping())"

# HITL endpoint functional
curl -f http://localhost:8000/v1/hitl/status | python3 -m json.tool

# Request submission functional
curl -X POST http://localhost:8000/v1/requests \
  -H "Content-Type: application/json" \
  -d '{"request_text": "health check test", "priority": "low"}' \
  -w "\nHTTP %{http_code}\n"
```

---

## Escalation

| Condition                           | Escalate to                         | Timeline         |
| ----------------------------------- | ----------------------------------- | ---------------- |
| Redis down > 5 min in production    | SRE Lead                            | Immediately      |
| Data loss confirmed                 | AI Governance Lead + SRE Lead       | Immediately      |
| TLS encryption broken in production | Security Lead                       | Immediately — P0 |
| PVC corruption                      | Platform Lead + Engineering Manager | Immediately      |
| GDPR/LGPD data exposure             | DPO + Legal                         | Within 1 h       |
