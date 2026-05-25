# RB-003 — HITL Gateway Recovery

**Owner:** SRE Lead + AI Governance Lead
**Severity scope:** P1 (pending approvals blocked or lost), P2 (degraded — in-memory fallback active)
**Last updated:** 2026-05-25
**PRR item:** PRR-OPS-002

---

## Overview

The HITL Gateway manages human-approval requests for consequential agent actions.
In production, requests are persisted in Redis (`HITLRedisStore`). This runbook covers
failure scenarios that affect HITL request durability, queue health, and capacity.

---

## Scenario 1 — Pod Restart (normal)

**Symptom:** Pod restarts; no HITL requests appear to be in-flight.

**Recovery:** No action required. Redis-backed requests survive the restart.

1. After the pod comes up, `expire_stale_requests()` runs at the next scheduled tick and
   cleans up any requests that expired during the downtime (they are moved to the
   `hitl:expired:{id}` archive, never auto-approved).
2. Verify the HITL queue depth metric is consistent with pre-restart state:
   ```bash
   redis-cli ZCARD hitl:pending
   ```
3. Cross-check with the Grafana CUJ-001 dashboard → "HITL Queue Depth" panel.

---

## Scenario 2 — Redis Failover

**Symptom:** Redis becomes unavailable. Pod startup logs: `Redis client creation failed`.
HITL gateway falls back to `InMemoryHITLStore`. Alert: `hitl_redis_unavailable`.

**Impact:** HITL requests submitted while Redis is down survive only until the next pod
restart. This is a **P2 degraded** state — human review still works, but durability is lost.

**Recovery steps:**

1. Confirm Redis is unreachable:
   ```bash
   redis-cli -u $REDIS_URL ping
   ```
2. If it is a transient network issue, wait for Redis to recover. The app will not
   automatically switch back — a pod restart is needed to re-initialize `HITLRedisStore`.
3. After Redis is healthy, perform a rolling restart:
   ```bash
   kubectl rollout restart deployment/template-service
   ```
4. Re-submit any HITL requests that were accepted during degraded mode (ops team must
   retrieve them from the in-memory audit log before the pod restarts):
   ```bash
   # Retrieve pending HITL events from audit log (InMemoryAuditStorage)
   curl http://<pod-ip>:8000/v1/hitl/pending
   ```
5. Verify the HITL gateway is now using Redis:
   ```bash
   redis-cli ZCARD hitl:pending
   ```

---

## Scenario 3 — Stuck Queue (requests not being decided)

**Symptom:** `hitl:pending` sorted set grows unboundedly; HITL approval latency SLO
(≤ 300 s p99) is breaching. Alert: `hitl_queue_depth_critical`.

**Investigation:**

```bash
# List all pending request IDs with their expiry timestamps
redis-cli ZRANGE hitl:pending 0 -1 WITHSCORES

# Inspect a specific request
redis-cli GET hitl:req:<request_id>
```

**Recovery:**

- If requests are genuinely waiting for human review, page the AI Governance Lead.
- If requests are stale (human reviewers unavailable), trigger manual expiry:
  ```bash
  # Force-expire a specific request via the admin endpoint
  curl -X POST http://<service>/v1/hitl/<request_id>/expire \
    -H "Authorization: Bearer $ADMIN_TOKEN"
  ```
- If no admin endpoint is available, use `expire_stale_requests()` via a one-off pod exec:
  ```bash
  kubectl exec -it <pod> -- python -c "
  import asyncio
  from src.api.rest.main import app
  gw = app.state.hitl_gateway
  result = asyncio.run(gw.expire_stale_requests())
  print('Expired:', result)
  "
  ```

---

## Scenario 4 — Capacity Exhausted

**Symptom:** API returns `503` with body `HITL request store at capacity`. Metric:
`hitl_active_requests` at or above `hitl_max_pending_requests` (default: 500).

**Immediate relief:**

1. Run `expire_stale_requests()` to evict any timed-out pending requests (see Scenario 3).
2. If the queue is legitimately full (500 concurrent human reviews), increase the cap via
   environment variable — **no deploy required**:
   ```bash
   kubectl set env deployment/template-service HITL_MAX_PENDING_REQUESTS=1000
   ```
3. Monitor the `hitl_active_requests` gauge and HITL approval latency p99.

**Root cause follow-up:** A persistently full queue indicates either:

- Insufficient human reviewer capacity → escalate to AI Governance Lead.
- Runaway agent submitting excessive HITL requests → check `hitl_active_requests` per `agent_id`.

---

## Scenario 5 — Redis Key Inspection and Manual Cleanup

**When to use:** Forensic investigation or emergency cleanup of specific requests.

```bash
# List all active HITL request keys
redis-cli KEYS "hitl:req:*"

# Inspect a request's JSON payload
redis-cli GET "hitl:req:<request_id>" | python -m json.tool

# List all archived (expired) requests
redis-cli KEYS "hitl:expired:*"

# Manually remove a stuck active request (last resort — creates audit gap)
# ALWAYS log the action in the incident ticket before running
redis-cli ZREM hitl:pending <request_id>
redis-cli DEL hitl:req:<request_id>
```

> **Warning:** Manually deleting keys bypasses the audit trail. Only do this under explicit
> AI Governance Lead approval. Document every key deleted in the incident record.

---

## Redis Key Schema Reference

| Key pattern         | Type        | TTL                       | Purpose                   |
| ------------------- | ----------- | ------------------------- | ------------------------- |
| `hitl:req:{id}`     | String/JSON | `expires_at` + 24 h grace | Active HITL request       |
| `hitl:pending`      | Sorted Set  | None (manual management)  | Index: score = expires_at |
| `hitl:expired:{id}` | String/JSON | 7 days                    | Archived expired request  |

TTL values are controlled by:

- `HITL_REDIS_TTL_GRACE_HOURS` (default: 24)
- `HITL_EXPIRED_TTL_DAYS` (default: 7)

---

## Escalation Path

| Condition                          | Escalate to              |
| ---------------------------------- | ------------------------ |
| Redis unavailable > 15 min         | Platform SRE on-call     |
| Queue stuck, reviewers unreachable | AI Governance Lead       |
| Requests manually deleted          | AI Governance Lead + DPO |
| Suspected agent abuse              | Security Lead            |
