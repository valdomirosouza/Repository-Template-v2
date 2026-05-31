# Runbook — PostgreSQL Connection Failure

**Runbook ID:** RB-004
**Severity:** P1–P2
**Owner:** SRE Lead
**Last reviewed:** 2026-05-31
**Reviewed by:** Tech Lead

---

## Symptoms

- Alert: `PostgreSQLDown` or `DatabaseConnectionPoolExhausted` firing
- API returning `503 Service Unavailable` or `500 Internal Server Error` on all data-dependent endpoints
- Logs contain: `sqlalchemy.exc.OperationalError`, `could not connect to server`, or `connection pool exhausted`
- Grafana: error rate spike correlated with DB connectivity loss; latency histogram shows timeout spike

---

## Impact

- **Who is affected:** all API consumers; agent pipeline blocked; HITL decisions cannot be persisted
- **Severity:** P1 if total connection loss; P2 if partial (pool exhaustion, intermittent timeouts)
- **SLO at risk:** `api-gateway` availability SLO (target ≥ 99.9%); `audit_log_write_success` (hard invariant — 100%)
- **Fallback:** `InMemoryAuditStorage` activates automatically in local dev but is **blocked in `app_env=production`** — do not rely on it

---

## Immediate Mitigation

1. **Check if infra is up:**
   ```bash
   kubectl get pods -n production -l app=postgresql
   docker compose ps postgresql   # local / staging
   ```
2. **Restart connection pool** (restores connections without restarting app pods):
   ```bash
   kubectl rollout restart deployment/api-gateway -n production
   ```
3. **Enable read-only mode** via feature flag if writes are the issue but reads are healthy:
   ```bash
   kubectl apply -f infrastructure/feature-flags/flags/read-only-mode.yaml
   ```
4. **If pool exhausted — scale down traffic** by reducing HPA `maxReplicas` temporarily to reduce concurrent connection demand.

---

## Root Cause Investigation

```bash
# Check DB pod status and recent events
kubectl get pods -n production -l app=postgresql
kubectl describe pod -n production -l app=postgresql

# Check DB logs for errors
kubectl logs -n production -l app=postgresql --tail=100

# Check connection pool metrics in Grafana
# Query: pg_stat_activity_count{datname="app_db"}
# Query: pg_stat_database_numbackends{datname="app_db"}

# Check app logs for connection errors
kubectl logs -n production -l app=api-gateway --tail=200 \
  | grep -E "OperationalError|connection pool|could not connect"

# Check network policy — DB reachable?
kubectl exec -n production deploy/api-gateway -- \
  nc -zv postgresql-service 5432
```

Key questions:

- Is the DB pod running and healthy, or has it crashed / OOM-killed?
- Is the issue pool exhaustion (too many connections) or network unreachability?
- Did a recent deploy change connection pool settings (`DB_POOL_SIZE`, `DB_POOL_TIMEOUT`)?
- Is disk full on the DB node (check `pg_database_size`)?

---

## Resolution

### Case A — DB pod crashed / OOM killed

```bash
# Restart DB pod
kubectl delete pod -n production -l app=postgresql
# PVC persists — data is not lost

# Verify recovery
kubectl get pods -n production -l app=postgresql -w
kubectl logs -n production -l app=postgresql --tail=50
```

### Case B — Connection pool exhausted

```bash
# Identify long-running queries blocking connections
kubectl exec -n production deploy/postgresql -- \
  psql -U app_user -c "SELECT pid, query, state, query_start FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;"

# Terminate blocking queries (use with care)
kubectl exec -n production deploy/postgresql -- \
  psql -U app_user -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND query_start < NOW() - INTERVAL '5 minutes';"
```

### Case C — Network / DNS unreachability

```bash
# Check service endpoint
kubectl get endpoints postgresql-service -n production

# Check network policy allows app → DB traffic
kubectl get networkpolicy -n production
```

### Case D — Disk full

```bash
kubectl exec -n production deploy/postgresql -- \
  psql -U app_user -c "SELECT pg_size_pretty(pg_database_size('app_db'));"

# Free space: vacuum + analyze
kubectl exec -n production deploy/postgresql -- \
  psql -U app_user -c "VACUUM ANALYZE;"
```

---

## Post-Incident

- [ ] Observe Golden Signals for 10 minutes after resolution — error rate < 1%, latency < 500ms p99
- [ ] Verify `audit_log_write_success` SLO is 100% — check for any missed audit events during outage
- [ ] If P1: open post-mortem in `docs/postmortems/` within 48 hours
- [ ] If pool exhaustion: review `DB_POOL_SIZE` and `DB_POOL_MAX_OVERFLOW` settings in `src/shared/config.py`
- [ ] Update this runbook with any new findings

---

## Prevention

- Set `DB_POOL_SIZE` and `DB_POOL_TIMEOUT` via env config; alert on `pg_stat_activity_count` approaching max connections
- Enable PgBouncer connection pooler for high-traffic services
- Add `pg_stat_statements` monitoring to detect long-running query patterns before they exhaust the pool
- Ensure DB pod has a `PodDisruptionBudget` and node affinity to prevent co-location issues
- Regularly test `make rollback` covers DB migration rollback path (RB-001)

---

## Escalation

| Situation                           | Escalation                                                             |
| ----------------------------------- | ---------------------------------------------------------------------- |
| DB pod will not start after restart | Page Tech Lead + SRE Lead                                              |
| Data loss or corruption suspected   | Page Tech Lead + DPO immediately                                       |
| Audit log gap detected              | Page Security Lead + AI Governance Lead (SOX CC4 breach if applicable) |
| Outage > 30 min                     | Page Engineering Manager                                               |
