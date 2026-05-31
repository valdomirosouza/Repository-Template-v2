# Skill: SOX Compliance

> **APPLICABILITY NOTICE**
> This skill is relevant ONLY for organizations publicly listed on U.S. stock exchanges
> (NYSE, NASDAQ) or otherwise subject to SEC reporting obligations under the
> Sarbanes-Oxley Act of 2002. Private companies, non-profits, and companies listed
> exclusively on non-U.S. exchanges have no legal obligation to follow SOX.
> If SOX does not apply to your organization, do not activate this skill and
> remove its row from the Skill Activation Table in CLAUDE.md §4.

## Purpose

Enforce Sarbanes-Oxley (SOX) controls on all financial data paths, access management,
and change evidence requirements — for SEC-regulated organizations only.

## When to Activate

- Any change to financial data write paths (`src/`, `services/`) — **only if SOX applies**
- Any change to audit logging (`guardrails/audit_logger.py`) — **only if SOX applies**
- Quarterly access reviews — **only if SOX applies**
- Pre-PRR for any service handling financial transactions — **only if SOX applies**

## Controls Checklist

### IT General Controls (ITGC)

- [ ] **CC1** — Access to production environment requires MFA and is role-limited.
- [ ] **CC2** — All access changes are logged in audit trail with approver identity.
- [ ] **CC3** — Segregation of duties: developer ≠ sole approver for financial paths. CODEOWNERS enforces minimum 2 approvers on `src/*`, `services/*`, `infrastructure/*`.
- [ ] **CC4** — Audit logs are immutable, tamper-evident, retained ≥ 7 years (ADR-0026).
- [ ] **CC5** — Production deployments traceable to an approved RFC with ticket ID in merge commit.
- [ ] **CC6** — Database encryption keys rotated annually; rotation documented in `docs/sox/key-rotation.md`.
- [ ] **CC7** — Privileged access reviewed quarterly; stale access revoked; documented in `docs/sox/access-review.md`.

### Application Controls

- [ ] Every financial transaction write emits an audit event with: `timestamp`, `actor_id`, `action`, `resource_id`, `request_id`, `correlation_id`, `financial_data=true`.
- [ ] Audit events published to append-only Kafka topic `audit.financial.events`.
- [ ] Audit consumer persists to PostgreSQL `audit_log` table with immutable flag (INSERT-only trigger).
- [ ] No `UPDATE` or `DELETE` on `audit_log` rows — verified by migration scan (harness SOX-02).
- [ ] PII masked via `guardrails/pii_filter.py` before any audit event is written.

### Change Evidence Controls

- [ ] Every production deployment records: deployer identity, RFC_ID, image digest (SHA-256), SBOM hash, timestamp — in `docs/change-log/`.
- [ ] Rollback events also recorded with: initiator, root cause (preliminary), incident ticket reference.
- [ ] CAB approval present for all Normal and Emergency changes before production pipeline executes.

## Evidence Artifacts

| Artifact            | Location                    | Frequency  | Owner         |
| ------------------- | --------------------------- | ---------- | ------------- |
| Audit log export    | `docs/sox/audit-exports/`   | Monthly    | DPO           |
| Access review       | `docs/sox/access-review.md` | Quarterly  | Security Lead |
| Change evidence log | `docs/change-log/`          | Per deploy | DevOps Lead   |
| Key rotation log    | `docs/sox/key-rotation.md`  | Annual     | Security Lead |

## Rollback Evidence

When a rollback occurs, the following MUST be recorded in `docs/change-log/`:

- Rollback timestamp and initiator identity
- Original RFC_ID and rollback RFC_ID
- Root cause (preliminary, within 1h)
- Incident ticket reference

## Spec Reference

`specs/compliance/sox-controls.md` — ITGC matrix, audit event schema, retention policy, acceptance criteria.
