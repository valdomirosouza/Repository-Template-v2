# ADR-0013 — Data Retention Policy

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** DPO, SRE Lead

---

## Context

LGPD Art. 16 and GDPR Art. 5(1)(e) require that personal data be retained no longer
than necessary for the stated processing purpose. The system generates several data
streams that contain or reference personal data:

- Operational logs (contain masked PII tokens; retain for debugging)
- Audit logs (contain anonymised agent action records; retain for compliance)
- Agent action history (contains references to user context; retain for review)
- User account data (governed by product requirements and deletion rights)
- Backup snapshots (contain all of the above)

Without an explicit retention policy enforced by automated lifecycle rules, data
accumulates indefinitely — creating both regulatory risk and unnecessary storage cost.

---

## Decision

Implement a **tiered retention schedule** enforced by automated lifecycle rules
in all storage systems. Manual deletion processes are not acceptable as a primary
mechanism.

| Data Type                         | Hot             | Warm                 | Deletion                      |
| --------------------------------- | --------------- | -------------------- | ----------------------------- |
| Operational logs (masked)         | 30 days         | 90 days              | Auto-purge at 90 days         |
| Audit logs (anonymised)           | 90 days         | 1 year               | Auto-purge at 1 year          |
| Agent action history              | 90 days active  | +30 days soft-delete | Hard-delete at day 120        |
| User account data                 | Active duration | 30 days post-closure | User-initiated or auto-expiry |
| Backup snapshots                  | 30-day rolling  | —                    | Auto-rotation                 |
| LLM interaction logs (anonymised) | 30 days         | —                    | Auto-purge at 30 days         |
| DPIA / RIPD documents             | Indefinite      | —                    | DPO manual review only        |

Lifecycle rules must be configured in: object storage buckets, database TTL indexes,
and log aggregator retention policies before any production release.

A monthly automated report confirms all scheduled purges executed successfully.
The SRE Lead is responsible for this report; the DPO reviews it quarterly.

---

## Consequences

### Positive

- LGPD Art. 16 and GDPR Art. 5(1)(e) obligations met by default
- Data subject erasure requests (LGPD Art. 18 / GDPR Art. 17) are satisfied within
  the retention window without additional manual work
- Storage costs are bounded and predictable
- Audit logs are retained long enough for regulatory investigation (1 year)
  while not accumulating indefinitely

### Negative / Trade-offs

- Automated purges must be tested before go-live; a misconfigured rule could
  delete data prematurely (mitigated by staging environment dry-run)
- Incident investigations are time-bounded by log retention; investigations must
  begin before the 90-day warm window closes

---

## Alternatives Considered

**Manual deletion on request only**
Rejected: relies on human memory; creates certain compliance gaps; does not satisfy
the "no longer than necessary" requirement of LGPD/GDPR when data accumulates
between deletion requests.

**Indefinite retention with access controls**
Rejected: directly violates LGPD Art. 16 and GDPR Art. 5(1)(e); creates growing
regulatory and reputational risk over time.
