# Data Protection Impact Assessment (DPIA) — Agent Memory

**GDPR Art. 35 | LGPD Art. 38 | Version:** 1.1 | **Date:** 2026-05-27
**Status:** Approved — DPO sign-off complete 2026-05-27

| Field      | Detail                                                 |
| ---------- | ------------------------------------------------------ |
| Activity   | Agent Persistent Memory (vector store + session cache) |
| Controller | Template Monorepo Org                                  |
| DPO        | Valdomiro Souza — valdomirojr@gmail.com                |
| Author     | Tech Lead                                              |
| ADR        | ADR-0017 (Agent Memory Architecture)                   |
| Spec       | specs/ai/agent-memory.md                               |

---

## Section 1 — Description of Processing

**Purpose:** Store agent context across sessions to enable recall of relevant
architectural decisions (specs, ADRs) and past HITL rejection patterns.

**Legal basis:**

- Art. 6(1)(f) GDPR — legitimate interest: improving system reliability and
  reducing repeated human review burden
- LGPD Art. 7(IX) — legitimate interest

**Data subjects:** System agents (non-natural persons). Indirect: users whose
requests triggered the agent actions that are logged as rejection patterns.

**Data categories:**

| Category                | PII Level | How processed                                   |
| ----------------------- | --------- | ----------------------------------------------- |
| Agent ID (UUID)         | L3        | Stored as-is — no natural person identifier     |
| Sprint context (masked) | L2→masked | pii_filter applied before every write           |
| HITL rejection feedback | L2→masked | pii_filter applied; no raw user content stored  |
| Spec/ADR content        | None      | Public internal documents; no PII               |
| Embedding vectors       | None      | Derived from masked text; not reversible to PII |
| Session metadata        | L3        | Session ID (UUID), TTL-evicted after 24 h       |

**Recipients:** Internal engineering and AI systems only. No third-party transfer.

**Third-country transfer:** No — pgvector and Redis are self-hosted on internal infra.

**Retention:**

- Vector store: 90 days (aligned with ADR-0013 data retention policy)
- Session cache: 24 h TTL (Redis auto-eviction)
- Deletion on erasure request: documents keyed by `agent_id` purged within 15 days

---

## Section 2 — Necessity and Proportionality

| Question                                        | Assessment                                                                                    |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Is processing necessary for the stated purpose? | Yes — without semantic recall, agents repeat errors requiring repeated human escalation       |
| Is data minimisation applied?                   | Yes — only masked content is stored; embeddings not reversible; TTL on session data           |
| Are data subject rights mechanisms in place?    | Yes — deletion workflow: query by agent_id, purge vector docs and session keys                |
| Is consent or another lawful basis established? | Yes — legitimate interest (Art. 6(1)(f) GDPR / LGPD Art. 7(IX)); no special-category data     |
| Is PII masking enforced structurally?           | Yes — `pii_filter.mask_text()` called at module boundary before every write; enforced in code |

---

## Section 3 — Risk Assessment

| Risk                                           | Likelihood | Impact | Score | Mitigation                                                                   | Residual   |
| ---------------------------------------------- | ---------- | ------ | ----- | ---------------------------------------------------------------------------- | ---------- |
| Unmasked PII persisted in vector store         | 2          | 3      | 6     | `pii_filter.mask_text()` mandatory at write boundary; test coverage enforced | Low        |
| Embedding vectors used to reverse-engineer PII | 1          | 2      | 2     | Embeddings computed from masked text only; reversibility not feasible        | Very Low   |
| Session cache data survives beyond TTL         | 1          | 2      | 2     | Redis TTL enforced by `SessionMemory.set()`; unit tested                     | Very Low   |
| Unauthorised access to stored agent context    | 2          | 2      | 4     | Postgres RLS + same access controls as audit_events; Redis AUTH enforced     | Low        |
| Data subject erasure request not fulfilled     | 1          | 3      | 3     | Deletion workflow documented; `agent_id` is indexed; 15-day SLA              | Low        |
| Spec/ADR content treated as PII in error       | 1          | 1      | 1     | Specs/ADRs contain no PII by policy; pii_filter passes them through cleanly  | Negligible |

---

## Section 4 — DPO Sign-Off

> **Sign-off complete — 2026-05-27. Agent Memory feature cleared for production.**

| Item                              | Status   | Sign-off date | DPO initials |
| --------------------------------- | -------- | ------------- | ------------ |
| Risk assessment reviewed          | Approved | 2026-05-27    | V.S.         |
| Retention periods approved        | Approved | 2026-05-27    | V.S.         |
| Erasure mechanism verified        | Approved | 2026-05-27    | V.S.         |
| No special-category data involved | Approved | 2026-05-27    | V.S.         |
| LGPD Art. 38 compliance confirmed | Approved | 2026-05-27    | V.S.         |

---

## Section 5 — Revision History

| Version | Date       | Author          | Change                                 |
| ------- | ---------- | --------------- | -------------------------------------- |
| 1.0     | 2026-05-27 | Tech Lead       | Initial draft                          |
| 1.1     | 2026-05-27 | Valdomiro Souza | DPO sign-off — all items approved (§4) |
