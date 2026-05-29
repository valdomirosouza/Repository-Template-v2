# Runbook: DLQ Messages Accumulating

**Alert:** `DLQAccumulating`
**Severity:** P1
**SLO impact:** Event Consumer — processing success rate (target 99.9%)
**Paging condition:** `increase(dlq_messages_total[5m]) > 0`

---

## What this alert means

Messages on `domain.request.created` have exhausted all retry attempts (default: 3) without
successful processing and have been routed to `domain.request.dlq`. Each DLQ-routed message
represents a request that is now in `failed` state with its error persisted — it will **not** be
reprocessed automatically. DLQ accumulation indicates a systemic failure in the processing path,
not a one-off transient error (those are handled by the retry loop before reaching the DLQ).

---

## Triage (first 5 minutes)

1. **Check Grafana** — open the Consumer dashboard; look at `dlq_messages_total` rate and
   `kafka_consumer_lag` for `consumer_group=template-consumer-group`.

2. **Identify the error class** — check structured logs for `dlq_routed=true`:

   ```bash
   kubectl logs -l app=api-gateway --since=10m | grep '"dlq_routed":true'
   ```

   Common patterns:
   - `LLM unavailable` / `circuit open` → LLM provider outage (see below)
   - `Audit write failed` → DB pool exhausted or schema mismatch (see below)
   - `Input rejected: injection guard` → potential attack vector; escalate to Security Lead
   - `timeout after 30s` → orchestrator taking too long (HPA may be under-scaled)

3. **Check downstream health:**
   ```bash
   kubectl get pods -l app=api-gateway
   curl -s http://localhost:8000/ready  # should return {"status":"ok"}
   ```

---

## Root cause playbooks

### A — LLM provider outage

Symptom: `error` field contains `circuit open` or connection-refused to Anthropic API.

1. Check Anthropic status page (out of band).
2. If confirmed outage: **do not replay** — wait for provider recovery.
3. Verify circuit breaker will auto-recover: `llm_circuit_breaker_reset_seconds = 60`.
4. After recovery, proceed to **Replay** below.

### B — Database / audit write failure

Symptom: `error` field contains `Audit write failed` or `pool exhausted`.

1. Check DB health:
   ```bash
   kubectl exec deploy/api-gateway -- curl -s localhost:8000/ready
   psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"
   ```
2. If pool exhausted: check `database_pool_size` setting vs. replica count. Consider increasing
   `max_size` or adding replicas.
3. If DB is unreachable: follow the DB recovery runbook (`docs/sre/runbooks/db-failure.md`).
4. After DB recovery: proceed to **Replay**.

### C — Injection guard rejection (potential attack)

Symptom: `error` field contains `Input rejected: injection guard`.

1. **Do not replay immediately** — this may be an active attack.
2. Extract the `request_id` values from DLQ logs and check the original payloads via
   `GET /v1/requests/{id}`.
3. Escalate to the Security Lead within 15 minutes (ISO 5.26 incident response).
4. If confirmed attack: block the source IP at WAF/load-balancer level before replaying.

---

## Replay procedure

Replaying routes DLQ messages back through the normal pipeline. Only replay when:

- The root cause is identified and fixed.
- The fix is confirmed healthy (readiness probe green, LLM/DB reachable).

```bash
# 1. Identify DLQ messages (requires Kafka CLI access):
kafka-console-consumer.sh \
  --bootstrap-server $KAFKA_BOOTSTRAP \
  --topic domain.request.dlq \
  --from-beginning \
  --max-messages 20

# 2. Re-publish to the original topic (per message):
kafka-console-producer.sh \
  --bootstrap-server $KAFKA_BOOTSTRAP \
  --topic domain.request.created \
  --property "parse.key=false"
# Paste the original envelope JSON (remove the dlq_error field first)

# 3. Monitor processing:
kubectl logs -l app=api-gateway -f | grep request_id=<id>

# 4. Confirm state transition:
curl http://localhost:8000/v1/requests/<request_id>
# Expected: {"status": "completed", ...}
```

**Note:** Before replaying, reset the request's status from `failed` back to `queued` if the
store entry still exists — otherwise the idempotency check will skip it:

```bash
# Via Redis CLI (if RedisRequestStore is in use):
redis-cli --tls -u $REDIS_URL GET "request:state:<request_id>"
redis-cli --tls -u $REDIS_URL SET "request:state:<request_id>" \
  '{"request_id":"<id>","status":"queued",...}'
```

---

## Escalation

| Condition                         | Action                                               | Owner         |
| --------------------------------- | ---------------------------------------------------- | ------------- |
| DLQ rate > 10/min for > 5 min     | P1 — page SRE Lead                                   | SRE Lead      |
| Injection guard rejection         | P1 — page Security Lead within 15 min                | Security Lead |
| Audit write failure in production | P0 — page Tech Lead (immutability invariant at risk) | Tech Lead     |
| DLQ rate > 0 after fix + replay   | P1 — escalate to Engineering Manager                 | Eng Manager   |

---

## Prevention

- **Retry loop** (`kafka_consumer_max_retries=3`, exponential backoff): absorbs transient failures
  before they reach the DLQ.
- **Circuit breaker** on LLM and DB clients: fails fast when a dependency is down, letting the
  retry loop backoff without hammering a degraded service.
- **`ConsumerStale` alert**: fires if `consumer_heartbeat_timestamp_seconds` is stale for >5 min
  AND consumer lag > 0 — catches a hung consumer before DLQ accumulation begins.

Spec: `specs/system/request-pipeline.md` · ADR: ADR-0003, ADR-0005
