# Runbook — Kafka Consumer Lag

**Runbook ID:** RB-005
**Severity:** P2–P3
**Owner:** SRE Lead
**Last reviewed:** 2026-05-31
**Reviewed by:** Tech Lead

---

## Symptoms

- Alert: `KafkaConsumerLagHigh` firing (`consumer_lag > 10 000` messages)
- Alert: `KafkaConsumerLagCritical` firing (`consumer_lag > 50 000` messages)
- Requests queued in `domain.request.created` topic not being processed
- Agent pipeline stalled — HITL requests not advancing; `RequestState` stuck in `QUEUED`
- Grafana: `event-consumer` SLO `consumer_lag` metric rising; `processing_success_rate` dropping

---

## Impact

- **Who is affected:** all async request flows; agent orchestration; HITL approval pipeline
- **Severity:** P2 if lag growing but consumer alive; P1 if consumer pod is down and lag unbounded
- **SLO at risk:** `event-consumer` consumer lag SLO (target max 10 000); `processing_success_rate` (target ≥ 99.9%)
- **Fallback:** `InMemoryBroker` activates when Kafka is unreachable — requests still accepted but not persisted to Kafka; switch to in-memory is automatic but data is lost on pod restart

---

## Immediate Mitigation

1. **Check consumer pod health:**
   ```bash
   kubectl get pods -n production -l app=event-consumer
   kubectl logs -n production -l app=event-consumer --tail=100
   ```
2. **If consumer is crash-looping — restart it:**
   ```bash
   kubectl rollout restart deployment/event-consumer -n production
   ```
3. **If lag is growing but consumer is alive — check partition assignment:**
   ```bash
   kubectl exec -n production deploy/kafka -- \
     kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
     --describe --group request-consumer-group
   ```
4. **Temporarily reduce upstream rate** by scaling down API gateway replicas if lag is unbounded and consumer cannot catch up.

---

## Root Cause Investigation

```bash
# Check consumer group lag across all partitions
kubectl exec -n production deploy/kafka -- \
  kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group request-consumer-group

# Check topic partition count and offsets
kubectl exec -n production deploy/kafka -- \
  kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic domain.request.created

# Check consumer throughput in Grafana
# Query: rate(kafka_consumer_records_consumed_total[5m])
# Query: kafka_consumer_lag_sum{group="request-consumer-group"}

# Check for poison-pill messages causing consumer to stall
kubectl logs -n production -l app=event-consumer --tail=500 \
  | grep -E "ERROR|WARN|DeserializationException|ProcessingException"

# Check Kafka broker health
kubectl get pods -n production -l app=kafka
kubectl exec -n production deploy/kafka -- \
  kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

Key questions:

- Is the consumer alive and consuming, just slowly? Or has it stopped entirely?
- Is one partition significantly lagging while others are healthy (partition imbalance)?
- Are there deserialization errors (schema mismatch after Avro schema change)?
- Did a recent deploy change consumer concurrency settings (`KAFKA_MAX_POLL_RECORDS`, `KAFKA_SESSION_TIMEOUT_MS`)?
- Is the Kafka broker itself under-resourced (check broker CPU/memory)?

---

## Resolution

### Case A — Consumer pod down / crash-looping

```bash
# Check crash reason
kubectl describe pod -n production -l app=event-consumer
kubectl logs -n production -l app=event-consumer --previous

# Restart
kubectl rollout restart deployment/event-consumer -n production

# Monitor recovery — lag should start decreasing
kubectl exec -n production deploy/kafka -- \
  kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group request-consumer-group
```

### Case B — Consumer alive but too slow (sustained lag growth)

```bash
# Scale up consumer replicas (ensure partition count >= replica count)
kubectl scale deployment/event-consumer -n production --replicas=3

# Verify partitions are rebalanced across new consumers
kubectl exec -n production deploy/kafka -- \
  kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group request-consumer-group
```

### Case C — Poison-pill message causing consumer to stall

```bash
# Identify the stuck offset
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group request-consumer-group

# Skip the bad message by resetting offset forward by 1
kubectl exec -n production deploy/kafka -- \
  kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group request-consumer-group \
  --topic domain.request.created \
  --reset-offsets --shift-by 1 --execute
```

⚠️ Skipping offsets discards the message — log the skipped offset and message key for post-mortem.

### Case D — Schema mismatch (Avro deserialization error)

```bash
# Check Schema Registry for schema version mismatch
curl http://schema-registry:8081/subjects/domain.request.created-value/versions

# Roll back schema if a breaking change was deployed
# Or update consumer to handle new schema version
```

---

## Post-Incident

- [ ] Confirm lag is decreasing and reaches 0 within SLO window
- [ ] Check `processing_success_rate` is recovering to ≥ 99.9%
- [ ] Verify no messages were permanently lost (DLQ check):
  ```bash
  kubectl exec -n production deploy/kafka -- \
    kafka-console-consumer.sh --bootstrap-server localhost:9092 \
    --topic domain.request.dead-letter --from-beginning --max-messages 20
  ```
- [ ] If P2: open post-mortem in `docs/postmortems/` within 5 business days
- [ ] Update this runbook with any new findings

---

## Prevention

- Set `KAFKA_MAX_POLL_RECORDS` conservatively (default 500); increase only with benchmark evidence
- Add DLQ (dead-letter queue) for messages that fail processing after 3 retries — prevents poison pills from blocking the partition
- Ensure partition count ≥ expected max consumer replicas (avoids idle consumers during scale-out)
- Monitor Schema Registry for breaking schema changes before they reach production consumers
- Test consumer scale-out path in staging before each release that touches the event pipeline

---

## Escalation

| Situation                                    | Escalation                                |
| -------------------------------------------- | ----------------------------------------- |
| Lag > 100 000 and not decreasing             | Page SRE Lead + Tech Lead                 |
| Consumer cannot be restarted                 | Page Tech Lead                            |
| Messages permanently lost (DLQ not draining) | Page Tech Lead + Engineering Manager      |
| Kafka broker down                            | Page SRE Lead immediately — P1 escalation |
