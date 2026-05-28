# Runbook: Kafka Consumer Lag

**Owner:** SRE Lead | **Reviewer:** Platform Lead | **Last updated:** 2026-05-28
**Alert:** `KafkaConsumerLagHigh` (>10k messages, 5 min)
**SLO reference:** `docs/sre/slo/slo.yaml` → `event-consumer.consumer_lag`, `event-consumer.processing_success_rate`
**Dashboard:** `infrastructure/monitoring/grafana/dashboards/golden-signals.json`

---

## Severity Classification

| Lag (messages) | Duration | Severity | Impact                                                 |
| -------------- | -------- | -------- | ------------------------------------------------------ |
| > 50 000       | > 5 min  | P1       | Pipeline stalled; end-to-end latency severely degraded |
| 10 000–50 000  | > 5 min  | P2       | Elevated; approaching SLO breach                       |
| > 0            | > 30 min | P3       | Slow consumer; investigate during business hours       |

---

## Step 1 — Assess Lag (< 5 minutes)

```bash
# Current lag per consumer group and topic
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum by (consumer_group, topic) (kafka_consumer_lag)' \
  | python3 -m json.tool

# Consumer pod health
kubectl get pods -n default -l app=api-gateway   # Python consumer (RequestConsumer)
kubectl get pods -n default -l app=event-worker  # Go consumer

# Check if DLQ is receiving messages
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(increase(dlq_messages_total[15m])) by (consumer_group, topic)' \
  | python3 -m json.tool

# Tail consumer logs for errors
kubectl logs -n default -l app=api-gateway --tail=100 --since=5m | grep '"level":"error"'
kubectl logs -n default -l app=event-worker --tail=100 --since=5m
```

---

## Step 2 — Identify Root Cause

### 2a. Consumer pod crash or OOMKill

```bash
kubectl describe pods -n default -l app=api-gateway | grep -A 3 "OOMKill\|Error\|CrashLoop"
kubectl describe pods -n default -l app=event-worker | grep -A 3 "OOMKill\|Error\|CrashLoop"

# Check recent restarts
kubectl get pods -n default -l app=api-gateway -o custom-columns=\
"NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount"
```

### 2b. Kafka broker degraded

```bash
# Broker pod health
kubectl get pods -n kafka -l app=kafka

# Under-replicated partitions (sign of broker failure)
kubectl exec -n kafka kafka-0 -- \
  kafka-topics.sh --bootstrap-server kafka:9092 \
  --describe --under-replicated-partitions 2>/dev/null | head -20

# Leader election in progress
kubectl exec -n kafka kafka-0 -- \
  kafka-topics.sh --bootstrap-server kafka:9092 \
  --describe --unavailable-partitions 2>/dev/null | head -20
```

### 2c. Consumer processing too slowly

```bash
# LLM latency spike causing slow processing
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.99, sum(rate(llm_call_duration_seconds_bucket[5m])) by (service, le))' \
  | python3 -m json.tool

# Agent semaphore saturated (blocking RequestConsumer)
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=agent_semaphore_waiting' | python3 -m json.tool

# DB connection pool exhausted
kubectl logs -n default -l app=api-gateway --tail=200 | grep -i "pool\|timeout\|asyncpg"
```

### 2d. Message poison pill (deserialization failure)

```bash
# DLQ growth is the primary indicator
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group api-gateway-consumer 2>/dev/null

# Look for repeated failures on the same offset
kubectl logs -n default -l app=api-gateway --tail=200 | \
  grep -E "DeserializationError|ParseError|offset"
```

---

## Step 3 — Remediation

### 3a. Scale consumer replicas (capacity issue)

```bash
# Scale api-gateway (Python RequestConsumer runs in the same pod)
kubectl scale deployment api-gateway -n default --replicas=5

# For event-worker (Go)
kubectl scale deployment event-worker -n default --replicas=3

# Monitor lag reduction over the next 5 minutes
watch -n 30 'curl -sG "http://localhost:9090/api/v1/query" \
  --data-urlencode "query=sum(kafka_consumer_lag)" | python3 -m json.tool'
```

### 3b. Partition rebalance (consumer group imbalance)

```bash
# List current partition assignments
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group api-gateway-consumer 2>/dev/null

# Trigger a rebalance by rolling restart of consumers
kubectl rollout restart deployment/api-gateway -n default
kubectl rollout status deployment/api-gateway -n default --timeout=120s
```

### 3c. Skip a poison pill message

Only execute after confirming the specific offset is unprocessable (checked logs, confirmed it's not a transient error):

```bash
# Get the current offset for the failing partition
TOPIC="domain.request.created"
PARTITION=0
GROUP="api-gateway-consumer"

# Move offset forward by 1 to skip the bad message
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group "$GROUP" --topic "$TOPIC:$PARTITION:$(( CURRENT_OFFSET + 1 ))" \
  --reset-offsets --execute 2>/dev/null

# The skipped message is automatically routed to the DLQ
```

**Governance note:** Skipping a message is a data-loss action in the context of that message's processing. Document the skipped offset, topic, and reason in a postmortem entry.

### 3d. Dead-letter queue recovery

Messages in the DLQ can be replayed after the root cause is fixed:

```bash
# List DLQ message count
kubectl exec -n kafka kafka-0 -- \
  kafka-run-class.sh kafka.tools.GetOffsetShell \
  --broker-list kafka:9092 --topic domain.request.created.dlq 2>/dev/null

# Replay from DLQ by resetting the consumer group offset to the beginning
kubectl exec -n kafka kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group api-gateway-consumer-dlq-replay \
  --topic domain.request.created.dlq \
  --reset-offsets --to-earliest --execute 2>/dev/null
```

### 3e. Broker recovery (broker pod failure)

```bash
# Check PersistentVolumeClaim health
kubectl get pvc -n kafka

# Force pod restart
kubectl delete pod kafka-0 -n kafka

# Monitor broker rejoin
kubectl logs -n kafka kafka-0 --follow | grep -i "leader\|ready\|started"
```

---

## Step 4 — Verify Recovery

```bash
# Lag should be decreasing
watch -n 30 'curl -sG "http://localhost:9090/api/v1/query" \
  --data-urlencode "query=sum(kafka_consumer_lag)" | python3 -m json.tool'

# Processing success rate should be above 99.9%
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=1 - (sum(rate(dlq_messages_total[5m])) / sum(rate(kafka_messages_consumed_total[5m])))' \
  | python3 -m json.tool
```

---

## Escalation

| Condition                           | Escalate to                    | Timeline      |
| ----------------------------------- | ------------------------------ | ------------- |
| Lag > 50k with no consumer activity | SRE Lead + Platform Lead       | Immediately   |
| Broker data loss suspected          | SRE Lead + Engineering Manager | Immediately   |
| DLQ growing with no clear cause     | Platform Lead                  | Within 30 min |
| Poison pill cannot be identified    | Tech Lead                      | Within 1 h    |
