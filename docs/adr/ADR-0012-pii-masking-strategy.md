# ADR-0012 — PII Masking Strategy

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Security Lead, DPO

---

## Context

The system processes personal data subject to LGPD (Lei 13.709/2018) and GDPR
(EU 2016/679). Two external boundaries create data-leakage risk:

1. **LLM API calls** — request payloads are sent to a third-party provider; any
   unmasked personal data becomes available to that provider's infrastructure
2. **Log aggregation** — structured logs are shipped to third-party observability
   platforms; unmasked PII in log records violates data minimisation requirements

A reactive, opt-in masking approach (engineers remember to mask before logging)
is insufficient — it relies on individual discipline and creates compliance gaps
whenever a new log statement or LLM call is added without review.

---

## Decision

Implement **mandatory interception-point masking** at three fixed boundaries:

| Boundary                          | Interception point | Implementation                                               |
| --------------------------------- | ------------------ | ------------------------------------------------------------ |
| Before every LLM API call         | LLM client wrapper | `src/guardrails/pii_filter.py`                               |
| Before every log write            | Structured logger  | `src/observability/logger.py` calls `pii_filter.mask_dict()` |
| Before every broker event publish | Kafka producer     | Producer calls `pii_filter.mask_dict()` before serialisation |

PII is classified into four levels (L1 Critical → L4 Public), defined in
`docs/privacy/pii-inventory.md`. Masking replaces detected values with typed
replacement tokens: `[EMAIL]`, `[CPF]`, `[NAME]`, `[IP]`, `[PHONE]`, `[TOKEN]`, `[CARD]`.

Tokens preserve the semantic structure of the field (the reader can tell what
kind of data was present) without exposing the actual value.

---

## Consequences

### Positive

- PII cannot reach external systems unless the interception point is explicitly bypassed
- Masking is applied uniformly regardless of which engineer wrote the LLM call or log statement
- Replacement tokens make log analysis possible without exposing personal data
- LGPD Art. 46 and GDPR Art. 25 (privacy by design) obligations are met structurally

### Negative / Trade-offs

- Small processing overhead at each interception point (regex scan per field)
- False positives are possible: a string matching an email pattern in a non-PII context
  will be masked (acceptable trade-off; err on the side of masking)
- Debugging is harder when log context is masked; mitigated by the internal audit log
  which retains identifiers for authorised incident investigation

---

## Alternatives Considered

**Opt-in masking (engineer responsibility)**
Rejected: scales poorly; compliance depends on code review catching every new
log statement and LLM call; gap is certain to appear in a growing codebase.

**Tokenisation vault (replace PII with opaque tokens stored in a vault)**
Considered for L1 data in a future ADR; deferred because vault infrastructure
adds operational complexity that is not yet justified by the current data volume.
Will be revisited as ADR-0014 when L1 tokenisation requirements are clearer.
