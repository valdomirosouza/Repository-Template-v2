# Runbook: API Gateway — High Error Rate

**Owner:** SRE Lead | **Reviewer:** Tech Lead | **Last updated:** 2026-05-28
**Alert:** `HighErrorRate` (>1% 5xx, 5 min) · `CriticalErrorRate` (>5% 5xx, 2 min)
**SLO reference:** `docs/sre/slo/slo.yaml` → `api-gateway.availability`
**Dashboard:** `infrastructure/monitoring/grafana/dashboards/golden-signals.json`

---

## Severity Classification

| Error rate | Duration | Severity                           | SLO impact                            |
| ---------- | -------- | ---------------------------------- | ------------------------------------- |
| > 5%       | > 2 min  | P1 — page on-call immediately      | Fast-burn; budget exhausts in ~2 days |
| 1–5%       | > 5 min  | P2 — investigate; prepare rollback | Slow-burn; monitor closely            |
| < 1%       | > 15 min | P3 — investigate at next sync      | Below SLO alert threshold             |

---

## Step 1 — Triage (< 5 minutes)

```bash
# 1a. Confirm error rate in Prometheus
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(http_requests_total{status=~"5.."}[2m])) / sum(rate(http_requests_total[2m]))' \
  | python3 -m json.tool | grep '"value"'

# 1b. Identify which endpoints are failing
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum by (route) (rate(http_requests_total{status=~"5.."}[5m])) > 0' \
  | python3 -m json.tool

# 1c. Check pod health
kubectl get pods -n default -l app=api-gateway
kubectl describe pods -n default -l app=api-gateway | grep -A 5 "Events:"

# 1d. Tail recent error logs
kubectl logs -n default -l app=api-gateway --tail=100 --since=5m \
  | grep '"level":"error"'
```

**Expected output:** A small set of failing routes (e.g. `/v1/requests`, `/v1/hitl/*`) and an error message pointing to a downstream dependency.

---

## Step 2 — Identify Root Cause

Work through these categories in order:

### 2a. Recent deployment

```bash
# Check if a deploy happened in the last 30 minutes
helm history api-gateway -n default | head -5
kubectl rollout history deployment/api-gateway -n default
```

If a recent deploy correlates with the error spike → **go to Step 4 (Rollback)** immediately for P1.

### 2b. Upstream dependency failure

```bash
# Check PostgreSQL connectivity
kubectl exec -n default deploy/api-gateway -- \
  python3 -c "import asyncpg, asyncio; asyncio.run(asyncpg.connect('$DATABASE_URL'))" 2>&1

# Check Redis connectivity
kubectl exec -n default deploy/api-gateway -- \
  python3 -c "import redis; redis.Redis.from_url('$REDIS_URL').ping()" 2>&1

# Check Kafka broker health
kubectl get pods -n kafka -l app=kafka
```

If a dependency is unreachable, check whether the **in-memory fallback** is active:

```bash
kubectl logs -n default -l app=api-gateway --tail=50 | \
  grep -i "fallback\|InMemory\|unavailable"
```

The in-memory fallback handles Redis/Kafka failures in dev — **it is blocked in production** (`app_env=production`). A production failure here is a P1 data-integrity incident.

### 2c. LLM provider failure

```bash
# Check circuit breaker status
kubectl logs -n default -l app=api-gateway --tail=100 | \
  grep -i "circuit\|anthropic\|llm\|timeout"

# LLM p99 latency — spikes cause cascading 503s
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.99, sum(rate(llm_call_duration_seconds_bucket[5m])) by (service, le))'
```

### 2d. Resource exhaustion

```bash
# CPU / memory pressure
kubectl top pods -n default -l app=api-gateway

# Agent semaphore saturation (returns 503 when full)
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=agent_semaphore_waiting' | python3 -m json.tool

# Rate limiting — check if client is hitting limits
kubectl logs -n default -l app=api-gateway --tail=100 | \
  grep '"status":429'
```

---

## Step 3 — Contain (P1 / P2 actions)

### 3a. Shed load temporarily

```bash
# Scale down HPA min replicas to reduce DB/Redis connection pressure
kubectl patch hpa api-gateway -n default \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/minReplicas","value":1}]'
```

### 3b. Scale up for capacity exhaustion

```bash
kubectl scale deployment api-gateway -n default --replicas=5
```

### 3c. Restart crashlooping pods

```bash
kubectl rollout restart deployment/api-gateway -n default
kubectl rollout status deployment/api-gateway -n default --timeout=120s
```

---

## Step 4 — Rollback

Use rollback when a recent deploy is the confirmed or probable cause, or when root cause is unclear and error rate is > 5%.

```bash
# Rollback to previous Helm release
helm rollback api-gateway -n default

# Verify rollback completed
kubectl rollout status deployment/api-gateway -n default --timeout=180s

# Confirm error rate is recovering
watch -n 10 'curl -sG "http://localhost:9090/api/v1/query" \
  --data-urlencode "query=sum(rate(http_requests_total{status=~\"5..\"}[2m])) / sum(rate(http_requests_total[2m]))" \
  | python3 -m json.tool | grep value'
```

Full rollback procedure: `skills/change-management/deploy-rollback.md`

---

## Step 5 — Verify Recovery

```bash
# Error rate should be back below 1%
# Run for 5 minutes after containment
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))'

# Health check endpoint
curl -f http://localhost:8000/health | python3 -m json.tool

# Check SLO error budget remaining
make agent-feedback-check
```

---

## Step 6 — Post-Incident

| Action                                                | Owner            | Timeline               |
| ----------------------------------------------------- | ---------------- | ---------------------- |
| File postmortem in `docs/postmortems/`                | On-call engineer | Within 48 h            |
| Update error-budget policy if budget < 10%            | SRE Lead         | Within 24 h            |
| Review recent deploy for the contributing change      | Tech Lead        | Before next deploy     |
| Check HITL queue for stale approvals caused by outage | HITL operator    | Within 1 h of recovery |

---

## Escalation

| Condition                                             | Escalate to          | Timeline    |
| ----------------------------------------------------- | -------------------- | ----------- |
| Error rate > 5% for > 5 min with no clear cause       | SRE Lead + Tech Lead | Immediately |
| Rollback fails or makes things worse                  | Engineering Manager  | Immediately |
| PII-handling endpoint returning errors (privacy risk) | DPO + Security Lead  | Within 1 h  |
| Error budget < 10% after incident                     | Engineering Manager  | Within 24 h |
