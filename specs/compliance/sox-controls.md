# SOX IT General Controls — Specification

**ID:** SPEC-sox-controls
**Version:** 1.0.0
**Status:** Approved (conditional — SEC-listed organizations only)
**Owner:** Tech Lead, Security Lead
**ADR:** ADR-0026

> **APPLICABILITY NOTICE**
> This spec is relevant ONLY for organizations publicly listed on U.S. stock exchanges
> (NYSE, NASDAQ) or otherwise subject to SEC reporting obligations under the
> Sarbanes-Oxley Act of 2002. If SOX does not apply, skip this spec entirely.

---

## 1. Purpose

Define the IT General Controls (ITGC) and application-level controls required to demonstrate SOX compliance for all services that process financial transactions, as enumerated in `services.yaml`.

---

## 2. Scope

All services listed in `services.yaml` that:

- Write to financial data tables in PostgreSQL
- Publish events to Kafka topics prefixed with `financial.` or `audit.financial.`
- Process payment, billing, or revenue data

---

## 3. ITGC Matrix

| Control ID | Control Name                   | Implementation                                                 | Evidence Location         |
| ---------- | ------------------------------ | -------------------------------------------------------------- | ------------------------- |
| CC1        | Production access requires MFA | IDP MFA policy + CODEOWNERS enforcement                        | docs/sox/access-review.md |
| CC2        | Access changes logged          | audit_logger.log_event() on all IAM changes                    | audit_log table           |
| CC3        | Segregation of duties          | CODEOWNERS min 2 approvers on src/, services/, infrastructure/ | GitHub branch protection  |
| CC4        | Immutable audit logs           | PostgreSQL INSERT-only trigger + Kafka infinite retention      | ADR-0026                  |
| CC5        | Deploy traceability            | RFC_ID in merge commit; cab-check CI gate                      | docs/change-log/          |
| CC6        | Encryption key rotation        | Annual rotation documented                                     | docs/sox/key-rotation.md  |
| CC7        | Privileged access review       | Quarterly review                                               | docs/sox/access-review.md |

---

## 4. Audit Event Schema

Every financial data write path MUST emit an audit event with the following schema. No optional fields may be omitted for financial events.

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-05-31T12:00:00Z",
  "actor_id": "usr_abc123",
  "action": "financial.transaction.created",
  "resource_id": "txn_uuid",
  "request_id": "req_uuid",
  "correlation_id": "corr_uuid",
  "financial_data": true,
  "amount_masked": true,
  "outcome": "success"
}
```

PII fields (actor_id, resource references) must be masked via `guardrails/pii_filter.py` before the event is written. The raw values are NOT stored in the audit log.

---

## 5. Audit Retention Policy

| Layer                                | Retention                    | Mechanism                                                |
| ------------------------------------ | ---------------------------- | -------------------------------------------------------- |
| PostgreSQL `audit_log`               | 7 years (rolling partition)  | Monthly partition archival                               |
| Kafka `audit.financial.events`       | Infinite (`retention.ms=-1`) | Topic config in `infrastructure/message-broker/`         |
| Cold storage (S3 Glacier equivalent) | 7 years                      | Monthly export script; SHA-256 manifest stored alongside |

Exports verified quarterly: SHA-256 of each export file compared against manifest. Discrepancies trigger a CC4 control failure incident.

---

## 6. Unit Tests

Tests in `tests/security/test_sox_controls.py` must assert:

- [ ] Every financial write path calls `audit_logger.log_event()` with `financial_data=True`
- [ ] No UPDATE or DELETE SQL statements exist in migrations targeting `audit_log`
- [ ] Audit events include all required schema fields (validated against JSON Schema)
- [ ] PII is masked before event write (pii_filter applied)

---

## 7. Acceptance Criteria

- [ ] SOX audit evidence package can be assembled from `docs/sox/` contents alone without additional investigation
- [ ] All CC1–CC7 controls have documented evidence artifacts with named owners
- [ ] Zero missing audit events for any financial write operation (verified by test suite)
- [ ] Cold storage export verified for the current quarter
- [ ] `audit_log` INSERT-only trigger present and tested in `tests/security/`
