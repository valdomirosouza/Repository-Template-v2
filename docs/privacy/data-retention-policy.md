# Data Retention Policy

**Owner:** DPO + SRE Lead
**Legal basis:** LGPD Art. 16, GDPR Art. 5(1)(e), GDPR Art. 17
**Last reviewed:** 2026-05-24
**Review cadence:** Quarterly

---

## Policy Statement

Personal data must not be retained longer than necessary for the stated processing
purpose. This policy defines mandatory retention periods for all data types processed
by this system, enforced by automated lifecycle rules in all storage systems.

Manual deletion processes are not acceptable as a primary mechanism — they are
error-prone and create certain compliance gaps.

---

## Retention Schedule

| Data Type                             | Hot Retention             | Warm Retention       | Deletion Method                            | Owner              |
| ------------------------------------- | ------------------------- | -------------------- | ------------------------------------------ | ------------------ |
| Operational logs (masked PII tokens)  | 30 days                   | 90 days              | Automated lifecycle rule on log aggregator | SRE Lead           |
| Audit logs (anonymised agent actions) | 90 days                   | 1 year               | Automated purge at 1 year                  | Security Lead      |
| Agent action history                  | 90 days active            | +30 days soft-delete | Hard-delete at day 120                     | Engineering Lead   |
| User account data                     | Active duration           | 30 days post-closure | User-initiated or automated expiry         | Product Owner      |
| Backup snapshots                      | 30-day rolling            | —                    | Automated rotation                         | SRE Lead           |
| LLM interaction logs (anonymised)     | 30 days                   | —                    | Automated purge at 30 days                 | AI Governance Lead |
| DPIA / RIPD documents                 | Indefinite (legal record) | —                    | DPO manual review only                     | DPO                |
| Security incident records             | 1 year                    | 3 years              | DPO + Security Lead joint review           | Security Lead      |

---

## Implementation Requirements

All storage systems must have lifecycle rules configured before go-live:

| Storage system                   | Configuration mechanism                                  |
| -------------------------------- | -------------------------------------------------------- |
| Object storage (S3/GCS)          | Bucket lifecycle policies                                |
| PostgreSQL                       | `pg_partman` partition expiry or scheduled deletion jobs |
| Log aggregator (Loki/CloudWatch) | Retention period configuration                           |
| Redis                            | TTL per key type                                         |
| Vector database                  | Collection TTL or scheduled purge                        |

---

## Deletion Verification

A monthly automated report confirms all scheduled purges executed successfully.

- **Produced by:** SRE Lead (automated job in CI)
- **Reviewed by:** DPO (quarterly)
- **Stored in:** `docs/postmortems/` (as a retention audit record)

If a purge fails, the SRE Lead is paged and the failure is treated as a P2 incident.

---

## Data Subject Deletion Requests

Under LGPD Art. 18 and GDPR Art. 17, data subjects may request deletion of their
personal data. Deletion requests are fulfilled within **15 business days**.

Process:

1. Request received by DPO at dpo@\<org-domain\>
2. Identity of requester verified
3. Engineering deletes user data across all storage systems
4. Deletion confirmed in writing to the data subject
5. Record of deletion retained (anonymised) for compliance purposes

---

## Quarterly Review

The DPO reviews this policy quarterly to ensure alignment with:

- Changes to LGPD / GDPR regulatory guidance
- New data types introduced since the last review
- Findings from the monthly automated purge report
- Data subject deletion request volume and response times
