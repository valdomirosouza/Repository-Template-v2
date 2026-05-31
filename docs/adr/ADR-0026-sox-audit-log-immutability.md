# ADR-0026 — SOX Audit Log Immutability Strategy

**Status:** Accepted (conditional — adopt only if organization is subject to SEC/SOX obligations)
**Date:** 2026-05-31
**Authors:** Tech Lead, Security Lead
**Reviewers:** AI Governance Lead, DevOps Lead

> **APPLICABILITY NOTICE**
> This ADR is relevant ONLY for organizations publicly listed on U.S. stock exchanges
> (NYSE, NASDAQ) or otherwise subject to SEC reporting obligations under the
> Sarbanes-Oxley Act of 2002. Private companies, non-profits, and companies listed
> exclusively on non-U.S. exchanges have no legal obligation to follow SOX.
> If SOX does not apply to your organization, skip this ADR entirely and remove the
> `skills/compliance/sox.md` activation row from CLAUDE.md §4.

---

## Context

SOX Section 302 and 404 require that public companies maintain accurate financial records with tamper-evident audit trails retained for a minimum of 7 years. For SEC-regulated entities, audit logs covering financial data write paths must be immutable — no UPDATE or DELETE operations must be possible after initial INSERT.

The existing `guardrails/audit_logger.py` provides audit event emission, but does not enforce immutability at the storage layer. PostgreSQL allows row-level modifications by default, and Kafka topics have configurable retention that may not meet the 7-year SOX requirement without explicit configuration.

For non-SOX organizations, the controls in this ADR represent recommended best practices for audit integrity, but carry no legal mandate.

---

## Decision

For SEC-regulated entities, implement a three-layer immutability strategy:

1. **PostgreSQL layer**: `audit_log` table with a DB-level INSERT-only trigger that raises an exception on any UPDATE or DELETE. The trigger is enforced at the database level, independent of application code.

2. **Kafka layer**: `audit.financial.events` topic with `retention.ms=-1` (infinite retention) and `cleanup.policy=delete` disabled. Separate consumer persists events to PostgreSQL and cold storage.

3. **Cold storage**: Monthly export of `audit_log` partitions to S3 Glacier (or equivalent immutable object storage) with SHA-256 manifest. Exports verified quarterly against PostgreSQL content.

Audit event schema (mandatory fields):

```json
{
  "timestamp": "ISO-8601",
  "actor_id": "masked-user-id",
  "action": "string",
  "resource_id": "uuid",
  "request_id": "uuid",
  "correlation_id": "uuid",
  "financial_data": false
}
```

---

## Consequences

- No UPDATE or DELETE on `audit_log` rows — immutability enforced at DB trigger level
- Query performance trade-off accepted: append-only table may grow large; partition by month
- Cold storage costs incurred for 7-year retention; budgeted under FinOps allocation (ADR-0020)
- `HITLRedisStore` audit events must be replicated to `audit_log` within the same transaction
- Encryption at rest (ADR-0018) applies to `audit_log`; `EncryptedField` wraps PII columns

**Skip this ADR entirely if SOX does not apply.**

---

## Alternatives Considered

**Application-level immutability only** — rejected because application code can be bypassed; DB-level enforcement is required for SOX evidence.

**Blockchain ledger** — rejected as operationally complex with no material SOX compliance advantage over a properly configured RDBMS with triggers.

**External audit log SaaS** — valid alternative for smaller teams, but increases vendor dependency and data residency complexity.
