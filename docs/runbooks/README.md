# Runbooks

Operational runbooks for this system. All runbooks follow a **blameless format**:
they focus on systems, processes, and improvements — not on individual mistakes.

---

## Runbook namespaces

Runbooks live in two namespaces so an ID never means two different things across domains
(see ADR-0033 and issue #195):

| Namespace    | Location             | Scope                                                                                                                                       |
| ------------ | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `RB-NNN`     | `docs/runbooks/`     | **Incident-response** runbooks — this index; the alert → runbook mapping below                                                              |
| `RB-SRE-NNN` | `docs/sre/runbooks/` | **SRE operational** runbooks (probe validation, agent-session recovery, …) — see [`docs/sre/runbooks/README.md`](../sre/runbooks/README.md) |

---

## Runbook Index

| ID     | Runbook                                                            | Severity | Owner              | Last reviewed |
| ------ | ------------------------------------------------------------------ | -------- | ------------------ | ------------- |
| RB-001 | [rollback-procedure.md](rollback-procedure.md)                     | P1–P2    | SRE Lead           | 2026-05-24    |
| RB-002 | [disaster-recovery.md](disaster-recovery.md)                       | P1       | SRE Lead           | 2026-05-24    |
| RB-003 | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                 | P1–P2    | AI Governance Lead | 2026-05-24    |
| RB-004 | [RB-004-db-connection-failure.md](RB-004-db-connection-failure.md) | P1–P2    | SRE Lead           | 2026-05-31    |
| RB-005 | [RB-005-kafka-consumer-lag.md](RB-005-kafka-consumer-lag.md)       | P2–P3    | SRE Lead           | 2026-05-31    |
| RB-006 | [RB-006-auth-failure.md](RB-006-auth-failure.md)                   | P1–P2    | Security Lead      | 2026-05-31    |

---

## Alert → Runbook Mapping

When a Prometheus alert fires, reach for the runbook linked below.

| Alert                              | Severity | Runbook                                                                                               |
| ---------------------------------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `CriticalErrorRate`                | P1       | [RB-001 rollback-procedure.md](rollback-procedure.md)                                                 |
| `HighErrorRate`                    | P2       | [RB-001 rollback-procedure.md](rollback-procedure.md)                                                 |
| `CriticalP99Latency`               | P1       | [RB-001 rollback-procedure.md](rollback-procedure.md)                                                 |
| `HighP99Latency`                   | P2       | [RB-001 rollback-procedure.md](rollback-procedure.md)                                                 |
| `APIGatewayAvailabilityFastBurn`   | P1       | [RB-001 rollback-procedure.md](rollback-procedure.md)                                                 |
| `APIGatewayAvailabilitySlowBurn`   | P2       | [RB-001 rollback-procedure.md](rollback-procedure.md)                                                 |
| `AuditLogWriteFailure`             | P1       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLAvailabilityFastBurn`         | P1       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLAvailabilitySlowBurn`         | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLQueueDepthCritical`           | P1       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLQueueDepthHigh`               | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLQueueDepthWarning`            | P3       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLApprovalTimeout`              | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLDecisionLatencyP95Critical`   | P1       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLDecisionLatencyP95Warning`    | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLNoApprovals`                  | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLRejectionRateHigh`            | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HITLWaitTimeHigh`                 | P3       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `CircuitBreakerOpen`               | P1       | [RB-004-db-connection-failure.md](RB-004-db-connection-failure.md)                                    |
| `CircuitBreakerHalfOpen`           | P2       | [RB-004-db-connection-failure.md](RB-004-db-connection-failure.md)                                    |
| `KafkaConsumerLagHigh`             | P2       | [RB-005-kafka-consumer-lag.md](RB-005-kafka-consumer-lag.md)                                          |
| `ConsumerLagCritical`              | P1       | [RB-005-kafka-consumer-lag.md](RB-005-kafka-consumer-lag.md)                                          |
| `ConsumerStale`                    | P2       | [RB-005-kafka-consumer-lag.md](RB-005-kafka-consumer-lag.md)                                          |
| `DLQMessagesGrowing`               | P2       | [RB-005-kafka-consumer-lag.md](RB-005-kafka-consumer-lag.md)                                          |
| `EventConsumerDLQBudgetBurning`    | P2       | [RB-005-kafka-consumer-lag.md](RB-005-kafka-consumer-lag.md)                                          |
| `AgentActionErrorRate`             | P2       | [RB-006-auth-failure.md](RB-006-auth-failure.md) + [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md) |
| `AgentMTTDHigh`                    | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `AgentMTTRHigh`                    | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `AgentAutonomousResolutionRateLow` | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `AutonomousResolutionRateCritical` | P1       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `AutonomousResolutionRateWarning`  | P3       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `LLMCallLatencyHigh`               | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `LLMTokenBudgetExceeded90Percent`  | P2       | [RB-003-hitl-recovery.md](RB-003-hitl-recovery.md)                                                    |
| `HighCPUUsage`                     | P2       | [disaster-recovery.md](disaster-recovery.md)                                                          |
| `HighMemoryUsage`                  | P2       | [disaster-recovery.md](disaster-recovery.md)                                                          |
| `ZeroRequestRate`                  | P1       | [RB-001 rollback-procedure.md](rollback-procedure.md) + [disaster-recovery.md](disaster-recovery.md)  |

---

## Service → Runbook Mapping

On-call quick reference: which runbook to reach for per affected service.

| Service          | Scenario                                                | Runbook                                   |
| ---------------- | ------------------------------------------------------- | ----------------------------------------- |
| `api-gateway`    | Deploy caused error rate spike / latency degradation    | [RB-001](rollback-procedure.md)           |
| `api-gateway`    | Total outage / all services unreachable                 | [RB-002](disaster-recovery.md)            |
| `api-gateway`    | 401/403 flood — users cannot authenticate               | [RB-006](RB-006-auth-failure.md)          |
| `agent-service`  | HITL queue backing up / approvals not flowing           | [RB-003](RB-003-hitl-recovery.md)         |
| `agent-service`  | Agent actions failing / autonomous resolution stalled   | [RB-003](RB-003-hitl-recovery.md)         |
| `event-consumer` | Kafka lag growing / pipeline stalled                    | [RB-005](RB-005-kafka-consumer-lag.md)    |
| `event-consumer` | DLQ accumulating / messages not processing              | [RB-005](RB-005-kafka-consumer-lag.md)    |
| `postgresql`     | API 500s correlated with DB — connection errors in logs | [RB-004](RB-004-db-connection-failure.md) |
| `postgresql`     | Pool exhausted — `OperationalError` in all services     | [RB-004](RB-004-db-connection-failure.md) |
| `all services`   | Infrastructure total failure / datacenter event         | [RB-002](disaster-recovery.md)            |

---

## Runbook Template

Copy this template when creating a new runbook:

```markdown
# Runbook — <Service/Incident Name>

**Runbook ID:** RB-NNN
**Severity:** P1 Critical / P2 High / P3 Medium / P4 Low
**Owner:** <Team>
**Last reviewed:** YYYY-MM-DD
**Reviewed by:** <Name — must be someone outside the authoring team>

---

## Symptoms

What does the on-call engineer observe?

- Alerts firing: <alert names>
- Dashboard signals: <what looks wrong>
- User reports: <if applicable>

---

## Impact

- Who is affected: <users / services / data flows>
- Severity: <P1/P2/P3/P4>
- SLO at risk: <SLO name from slo.yaml>

---

## Immediate Mitigation

Steps to reduce impact RIGHT NOW — before root cause is found.

1. <Step 1>
2. <Step 2>

---

## Root Cause Investigation

Diagnostic commands and queries to run.

\`\`\`bash

# Check pod status

kubectl get pods -n <namespace>

# Check recent logs

kubectl logs -n <namespace> <pod> --tail=100

# Check Golden Signals dashboard

# URL: <Grafana dashboard URL>

\`\`\`

Key questions to answer:

- When did the issue start? (check `trace_id` in logs)
- Which component is the failure origin?
- Is the failure isolated or cascading?

---

## Resolution

Steps to fully resolve the issue.

1. <Step 1>
2. <Step 2>

---

## Post-Incident

Actions after resolution:

- [ ] Monitoring window: observe Golden Signals for <duration> after fix
- [ ] If P1 or P2: open post-mortem in `docs/postmortems/`
- [ ] Update this runbook with any new findings
- [ ] File ticket for any long-term prevention work

---

## Prevention

Long-term fixes or improvements to prevent recurrence.

- <Prevention item 1>
- <Prevention item 2>
```

---

## Blameless Principles

1. **Systems over individuals** — runbooks describe what systems did, not what people did wrong
2. **Learning over blame** — every incident is an opportunity to improve the system
3. **Contributing factors** — identify all contributing factors, not a single root cause
4. **Prevention over punishment** — post-mortems result in action items, not performance reviews
5. **Psychological safety** — engineers must feel safe to report incidents promptly and accurately

---

## Review Requirements

Every runbook must be:

- Reviewed by someone **outside the authoring team** before it is considered active
- Re-reviewed after any incident that reveals a gap in the runbook
- Re-reviewed at least **annually** as part of the PRR process
