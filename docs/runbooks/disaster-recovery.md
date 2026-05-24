# Runbook — Disaster Recovery

**Runbook ID:** RB-002
**Severity:** P1
**Owner:** SRE Lead + Tech Lead
**Last reviewed:** 2026-05-24

---

## RPO / RTO Targets

| Service        | RPO (max data loss)         | RTO (max downtime) |
| -------------- | --------------------------- | ------------------ |
| api-gateway    | 0 (stateless)               | 5 minutes          |
| agent-service  | 15 minutes                  | 15 minutes         |
| event-consumer | 0 (Kafka replay)            | 10 minutes         |
| Database       | 1 hour (last backup)        | 30 minutes         |
| Audit log      | 0 (append-only, replicated) | 15 minutes         |

---

## DR Activation Criteria

A disaster is declared by the **Tech Lead or SRE Lead** when:

- Full cloud region / provider outage affecting all services
- Data corruption affecting production database
- Security incident requiring immediate service shutdown
- Complete message broker failure with no failover available

**Activation:** announce in incident channel, page Engineering Manager, update status page.

---

## Scenario 1 — Full Region / Cloud Provider Outage

**Detection:** All health checks failing; cloud provider status page shows outage.

**Response:**

1. Confirm outage is provider-side (not a misconfiguration): check provider status page
2. Activate failover region if multi-region is configured:
   ```bash
   # Update DNS to point to failover region
   # (procedure depends on DNS provider — document here)
   ```
3. If no failover region: notify stakeholders; set status page to "Investigating"
4. Monitor provider status; restore once region recovers
5. After recovery: verify all services healthy; replay any Kafka events missed during outage

---

## Scenario 2 — Database Corruption or Data Loss

**Detection:** Application errors referencing data inconsistency; integrity check failures.

**Response:**

1. Immediately pause all writes to the affected database:
   ```bash
   # Scale down write-path services
   kubectl scale deployment agent-service --replicas=0 -n production
   ```
2. Assess scope: which tables/records are affected?
3. Restore from latest backup:
   ```bash
   # Restore procedure (document specific commands for your DB provider)
   uv run alembic downgrade <last-known-good-revision>
   # Restore data from backup snapshot
   ```
4. Validate restored data integrity
5. Scale services back up; monitor for 30 minutes
6. Post-mortem: identify corruption source; implement prevention

---

## Scenario 3 — Message Broker (Kafka) Complete Failure

**Detection:** Consumer lag alerts firing; producers returning errors; no messages flowing.

**Response:**

1. Check Kafka broker health:
   ```bash
   kubectl get pods -n kafka
   kubectl logs -n kafka kafka-0 --tail=100
   ```
2. If broker pods are crashed: attempt restart:
   ```bash
   kubectl rollout restart statefulset/kafka -n kafka
   ```
3. If persistent failure: activate DLQ replay procedure after recovery
4. Producers buffer events during outage (verify `max.block.ms` configuration)
5. After recovery: monitor consumer lag until fully caught up
6. Verify no events were lost (compare produced vs consumed counts)

---

## Scenario 4 — LLM Provider API Outage

**Detection:** `llm_call_errors_total` spiking; agent-service returning 503s.

**Response:**

1. Enable fallback mode (smaller/cached responses):
   ```bash
   # Set feature flag to disable full LLM reasoning
   kubectl set env deployment/agent-service LLM_FALLBACK_MODE=true -n production
   ```
2. Route HITL flows to manual processing (disable auto-routing)
3. Monitor provider status page
4. After recovery: disable fallback mode; monitor for 15 minutes
5. Replay any requests that failed during outage if idempotent

---

## Scenario 5 — Security Incident Requiring Immediate Shutdown

**Detection:** Security Lead or external report indicating active breach or data exfiltration.

**Response:**

1. **Immediately** page Security Lead + Engineering Manager
2. Take affected services offline:
   ```bash
   kubectl scale deployment <affected-service> --replicas=0 -n production
   ```
3. Preserve all logs and audit records (do NOT delete anything)
4. Rotate all secrets and API keys immediately
5. Notify DPO — GDPR 72h breach notification clock starts
6. Do not restore service until Security Lead confirms it is safe
7. Post-mortem and regulatory notification per DPO guidance

---

## Communication Plan

| Audience                           | Channel                | Owner            | Timing            |
| ---------------------------------- | ---------------------- | ---------------- | ----------------- |
| Engineering team                   | Incident Slack channel | On-call engineer | Immediately       |
| Management                         | Direct message         | SRE Lead         | Within 15 minutes |
| External users                     | Status page update     | Product Owner    | Within 30 minutes |
| DPO (if personal data affected)    | Direct                 | Tech Lead        | Immediately       |
| Regulatory authority (GDPR breach) | Formal notification    | DPO              | Within 72 hours   |

---

## Backup Verification

Monthly procedure to confirm backup integrity:

1. Restore latest backup to a test environment
2. Run data integrity checks
3. Confirm restoration meets RPO target
4. Document result in `docs/postmortems/` (as a maintenance record)

---

## DR Drill Schedule

Quarterly DR drill — one scenario per quarter, rotating through all five scenarios.
Results documented in `docs/postmortems/YYYY-MM-DD-dr-drill-<scenario>.md`.
