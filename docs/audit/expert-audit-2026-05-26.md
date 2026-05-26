# Expert Audit — 2026-05-26

**Reviewer:** Senior Software Engineer (AI-assisted)
**Baseline:** v1.1.1 (`ff34506`)
**Resolved in:** v1.2.0 (`d2fb36d`) — tag `v1.2.0`
**GitHub Release:** https://github.com/valdomirosouza/template-monorepo/releases/tag/v1.2.0

---

## Scope

Full review of markdowns, documentation, skills, harness gate files, guardrails, and source
code. 18 findings across four severity tiers. All resolved before this PR was opened.

---

## Findings

### Critical — 5 issues · commit `231ada4`

| #   | Location                                              | Finding                                                                                                           |
| --- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 1   | `harness/code-check.yml`                              | SAST gate used `semgrep \|\| true` — silently passed on any failure; replaced with `bandit -r src/ -ll`           |
| 2   | `skills/ai/guardrails.md`, `skills/privacy/pii.md`    | `[TOKEN]` classified as L3 (Internal); JWT/session tokens are L2 (Sensitive)                                      |
| 3   | `src/guardrails/prompt_injection_guard.py`            | Dead `_check_length()` method defined but never called in `validate()`                                            |
| 4   | `harness/code-check.yml`, `harness/staging-check.yml` | pii-scan gate had `\|\| true` bypass; staging-check regex `[^\[MASKED]` was a character class, not a prefix check |
| 5   | `src/agents/hitl_gateway.py`                          | `ACTIVE_HITL_REQUESTS` gauge never decremented on `APPROVED`/`REJECTED` decisions                                 |

### High — 5 issues · commit `3c6b24c`

| #   | Location                                                                                | Finding                                                                                                       |
| --- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 6   | `src/agents/harness/coordinator.py` · `_generate()`                                     | User-supplied text embedded in LLM prompt without PII masking — violated three mandatory interception points  |
| 7   | `src/agents/harness/coordinator.py` · `_escalate_to_hitl()`, `_review_spec_with_hitl()` | Payload and `context_summary` passed to `HITLRequest` without `mask_dict()` — PII flowed to reviewer UI       |
| 8   | `src/agents/hitl_gateway.py` · `record_decision()`                                      | `ACTIVE_HITL_REQUESTS` gauge not decremented in the non-expired branch                                        |
| 9   | `harness/code-check.yml` · `spec-compliance`                                            | Gate read `.git/MERGE_MSG` (only populated during local merges) then fell back to `/dev/null` — always passed |
| 10  | `src/agents/harness/coordinator.py` · `_run_simplified()`                               | Default success criterion was vague and not independently testable by the Evaluator                           |
| 15  | `skills/privacy/pii.md`                                                                 | Documented a `L2_FIELD_NAMES` registry that doesn't exist in `pii_filter.py` — false sense of security        |

### Medium — 4 issues · commit `cebc5b1`

| #   | Location                                                  | Finding                                                                                                                          |
| --- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| M1  | `src/agents/hitl_gateway.py` · `record_decision()`        | `APPROVED`/`REJECTED` requests saved back to `_active` but never archived — `pending_count()` inflated; `_active` grew unbounded |
| M2  | `src/observability/metrics.py` · `record_hitl_decision()` | Double gauge decrement: `metrics.py` and `hitl_gateway.py` both called `.dec()` after the high-severity fix                      |
| M3  | `harness/doc-check.yml` · `spec-exists`, `adr-current`    | Same `.git/MERGE_MSG` anti-pattern as Issue 9 — both gates silently passed in CI                                                 |
| M4  | `src/guardrails/audit_logger.py`                          | `InMemoryAuditStorage.query()` filter logic (4 filters + limit) had zero unit tests                                              |

### Low — 4 issues · commit `f36a51c`

| #   | Location                                         | Finding                                                                                                                       |
| --- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| L1  | `src/api/rest/routers/hitl.py` · `hitl_status()` | Accessed `gateway._requests` — removed in the HITLStore refactoring; raises `AttributeError` 500 on every `/hitl/status` call |
| L2  | `CHANGELOG.md`                                   | `[Unreleased]` section empty after three fix batches were committed to `main`                                                 |
| L3  | `src/guardrails/action_limits.py`                | `check_scope_limit()` and unified `check()` — critical guardrail path at 30% coverage with no tests                           |
| L4  | `src/api/rest/routers/hitl.py`                   | `submit_decision` 404 error path and `get_hitl_gateway` 503 path had no tests                                                 |

---

## Test Impact

| Metric        | Before  | After   |
| ------------- | ------- | ------- |
| Unit tests    | 146     | 171     |
| Coverage      | 79.86%  | 85.73%  |
| Coverage gate | failing | passing |

---

## Files Changed (by commit)

```
231ada4  harness/code-check.yml · harness/staging-check.yml
         skills/ai/guardrails.md · skills/privacy/pii.md
         src/guardrails/prompt_injection_guard.py

3c6b24c  src/agents/harness/coordinator.py
         src/agents/harness/models.py
         src/agents/hitl_gateway.py
         harness/code-check.yml
         skills/privacy/pii.md
         tests/unit/agents/test_hitl_gateway.py

cebc5b1  src/agents/hitl_gateway.py
         src/observability/metrics.py
         harness/doc-check.yml
         tests/unit/agents/test_hitl_gateway.py
         tests/unit/guardrails/test_audit_logger.py  (new)

f36a51c  src/api/rest/routers/hitl.py
         CHANGELOG.md
         tests/unit/guardrails/test_action_limits.py  (new)
         tests/unit/api/test_hitl_router.py           (new)
```
