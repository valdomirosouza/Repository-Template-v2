# Data Retention Spec

**Status:** Approved | **Owner:** DPO | **Last updated:** 2026-05-24
**ADR references:** ADR-0013 (Data Retention Policy), ADR-0012 (PII Masking)

---

## Retention Schedule

| Data category             | Storage system    | Retention period | Deletion method      | Legal basis                      |
| ------------------------- | ----------------- | ---------------- | -------------------- | -------------------------------- |
| L1 PII (masked tokens)    | PostgreSQL        | 90 days          | Hard delete          | LGPD Art. 16 / GDPR Art. 5(1)(e) |
| L2 PII (masked tokens)    | PostgreSQL        | 1 year           | Hard delete          | LGPD Art. 16 / GDPR Art. 5(1)(e) |
| Agent audit records       | Append-only store | 5 years          | Archive after 1 year | LGPD Art. 37 / GDPR Art. 5(2)    |
| Application logs (masked) | Log aggregator    | 90 days          | TTL expiry           | Operational necessity            |
| Kafka events              | Kafka             | 7 days           | Topic TTL            | Operational necessity            |
| Kafka DLQ events          | Kafka             | 30 days          | Topic TTL            | Failure recovery                 |
| Vector DB embeddings      | Vector DB         | 1 year           | Hard delete          | Pseudonymised; legitimate use    |
| Redis session cache       | Redis             | Session lifetime | TTL expiry           | Operational necessity            |
| Backup snapshots          | Object storage    | 30 days          | Automated purge      | RPO requirement                  |
| DPIA / RIPD documents     | Docs repository   | Indefinite       | Manual; DPO approval | Regulatory record                |

---

## Implementation Requirements

### Automated Deletion

All time-bounded retention tiers must be enforced by automated jobs — manual deletion is not acceptable for compliance.

| Mechanism                | Used for                              | Implementation                                              |
| ------------------------ | ------------------------------------- | ----------------------------------------------------------- |
| PostgreSQL TTL job       | L1/L2 masked fields in application DB | Scheduled job; `DELETE WHERE created_at < NOW() - INTERVAL` |
| Kafka topic TTL          | All Kafka topics                      | Topic config: `retention.ms`                                |
| Redis TTL                | Session and cache keys                | Key-level TTL set at write time                             |
| Log aggregator TTL       | Structured logs                       | Index/stream TTL configuration                              |
| Object storage lifecycle | Backup snapshots                      | Bucket lifecycle policy                                     |

### Deletion Verification

After every scheduled deletion run:

1. Log the count of records deleted per category
2. Spot-check: confirm no records older than retention threshold remain
3. Emit metric: `data_retention_deleted_total{category}` and `data_retention_overdue_total{category}`
4. Alert if `data_retention_overdue_total > 0` for any L1/L2 category

---

## Right to Erasure (LGPD Art. 18 / GDPR Art. 17)

When a data subject submits an erasure request:

1. DPO receives and validates the request
2. Engineering identifies all systems containing the subject's data (use PII inventory as guide)
3. Hard-delete L1/L2 fields from PostgreSQL within **15 days**
4. Invalidate Vector DB embeddings derived from subject's data
5. Pseudonymise or redact audit records (audit structure preserved; subject fields replaced with `[ERASED]`)
6. Confirm deletion to DPO in writing
7. DPO responds to data subject within **15 days** of request (LGPD requirement)

**Exception:** Audit records required for legal proceedings are retained per legal hold; DPO must approve any legal hold extension.

---

## Quarterly Review

DPO reviews retention compliance quarterly:

1. Verify automated deletion jobs ran successfully (check `data_retention_deleted_total` metrics)
2. Confirm no L1/L2 records exceed retention threshold
3. Review any erasure requests received and confirm timely completion
4. Update retention schedule if regulatory requirements changed
5. Document review outcome in `docs/postmortems/YYYY-MM-DD-retention-review.md`

---

## Legal Hold Procedure

When a legal hold is required:

1. Legal team notifies DPO + Tech Lead in writing
2. Tech Lead creates a hold record identifying the data in scope
3. Automated deletion is suspended for held data only
4. Hold is reviewed quarterly; lifted when legal proceeding concludes
5. On lift: normal retention schedule resumes; overdue records deleted within 30 days
