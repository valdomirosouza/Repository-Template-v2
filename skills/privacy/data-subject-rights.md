# Skill — Data Subject Rights

**Owner:** DPO | **Reviewer:** Security Lead | **Status:** Active | **Last updated:** 2026-05-28

Activate this skill when implementing or responding to data subject requests (access,
deletion, portability, rectification, objection) under GDPR Art. 12–22 or LGPD Art. 17–22.

**Related:** `skills/privacy/pii.md`, `skills/privacy/lgpd.md`, `skills/privacy/gdpr.md`,
`docs/privacy/data-processing-register.md`, `specs/privacy/data-retention.md`

---

## Rights and SLAs

| Right                             | GDPR Article | LGPD Article | Response SLA   | Notes                                                    |
| --------------------------------- | ------------ | ------------ | -------------- | -------------------------------------------------------- |
| Access (Subject Access Request)   | Art. 15      | Art. 18(I)   | 30 days        | Extend 60 days with notice if complex                    |
| Erasure ("right to be forgotten") | Art. 17      | Art. 18(VI)  | 30 days        | Exceptions apply (legal obligation, legitimate interest) |
| Portability                       | Art. 20      | Art. 18(V)   | 30 days        | Machine-readable format (JSON, CSV)                      |
| Rectification                     | Art. 16      | Art. 18(III) | 30 days        | Correct inaccurate data                                  |
| Objection to processing           | Art. 21      | Art. 18(II)  | Immediate stop | Unless overriding legitimate interest                    |
| Restriction of processing         | Art. 18      | Art. 18(IV)  | Immediate      | Mark data as restricted; do not delete yet               |

---

## Handling a Request

### Step 1 — Identity verification

Before acting on any request, verify the data subject's identity:

- Email verification + knowledge-based question, OR
- Government ID if the request involves sensitive data (L1/L2)
- Log the verification method in `docs/privacy/data-processing-register.md`

### Step 2 — Locate the data

Personal data may exist in:

- PostgreSQL (`domain_entities`, `audit_events` tables)
- Redis (session memory, HITL pending requests — TTL 24h)
- Kafka topics (short-lived; check retention: `request.created.v1` = 7 days)
- Vector store (`agent_memory_documents` table — 90-day retention)
- Application logs (30-day retention; structured JSON)
- Backup/archive stores (per `docs/privacy/data-retention-policy.md`)

### Step 3 — Execute the request

**Access request:** Export all rows in PostgreSQL where `user_id = ?` as JSON.
Include: request history, audit events, stored context. Exclude: data belonging to
other users that appears in shared context (mask those with `[REDACTED]`).

**Erasure request:**

```sql
-- Soft-delete first (30-day grace period per data-retention-policy.md)
UPDATE domain_entities SET status = 'DELETED', deleted_at = NOW() WHERE user_id = ?;
-- Hard-delete after grace period via retention_job.py
```

For vector store: delete rows in `agent_memory_documents` where `source` contains user_id.
For Redis: call `DEL` on the session key and any HITL request keys associated with the user.

**Portability request:** Export as JSON using the same query as access, wrap in a
standard envelope (see `docs/privacy/data-processing-register.md` export format).

### Step 4 — Notify downstream processors

If the data was shared with third-party processors (LLM provider, analytics):

- Anthropic DPA: submit erasure request per the DPA procedure
- Log the notification in `docs/privacy/data-processing-register.md`

### Step 5 — Respond to the data subject

Reply within the SLA (see table above). Include:

- Confirmation of action taken
- Categories of data processed
- Contact details for the DPO if further questions

### Step 6 — Log the request

Every data subject request must be logged in `docs/privacy/data-processing-register.md`:

- Request type, date received, date responded
- Identity verification method
- Actions taken
- Any exceptions applied and their legal basis

---

## Exceptions

The following grounds may allow refusal or restriction of a request. Always consult
the DPO before applying an exception:

| Exception                                  | Applicable rights    | Legal basis                          |
| ------------------------------------------ | -------------------- | ------------------------------------ |
| Legal obligation to retain                 | Erasure              | GDPR Art. 17(3)(b); LGPD Art. 16(I)  |
| Legitimate interest overrides              | Objection            | GDPR Art. 21(1); LGPD Art. 10        |
| Freedom of expression / journalism         | Erasure              | GDPR Art. 17(3)(a)                   |
| Ongoing litigation                         | Erasure, Restriction | Legal hold policy                    |
| Manifestly unfounded or excessive requests | Any                  | GDPR Art. 12(5) — document reasoning |

---

## Automated Decision-Making (Art. 22 / LGPD Art. 20)

If the HITL gateway ever allows a fully automated decision with significant effects on a
data subject (no human in the loop), the data subject has the right to:

- Human review of the decision
- An explanation of the logic involved
- The ability to contest the decision

**This right is automatically satisfied** when `HITL (default)` mode is active — every
consequential action requires explicit human approval. If `HOTL` or `FULL` autonomy is
enabled, verify this right is addressed before activation (ADR-0015).
