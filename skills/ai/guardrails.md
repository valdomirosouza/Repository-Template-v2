# Skill — AI Guardrails

**Owner:** Security Lead | **Reviewer:** AI Lead | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill for any agent implementation, guardrail change, or AI safety review.

---

## The Four Mandatory Guardrail Layers

All four must pass in order before any agent action executes. No bypass path exists.

| Layer              | File                                       | Purpose                                             |
| ------------------ | ------------------------------------------ | --------------------------------------------------- |
| L1 PII Filter      | `src/guardrails/pii_filter.py`             | Mask PII before LLM call, log write, broker publish |
| L2 Injection Guard | `src/guardrails/prompt_injection_guard.py` | Reject instruction-override attempts                |
| L3 Action Limits   | `src/guardrails/action_limits.py`          | Enforce rate limits and scope restrictions          |
| L4 Audit Logger    | `src/guardrails/audit_logger.py`           | Immutable record written before action executes     |

Full spec: `specs/ai/guardrails.md`

---

## Using `pii_filter.py`

Three mandatory interception points (ADR-0012):

1. **Pre-LLM call** — mask agent context before constructing the prompt
2. **Pre-log write** — mask all structured log fields
3. **Pre-broker publish** — mask event payload before Kafka produce

```python
masked_payload = pii_filter.mask_dict(raw_payload)
# Only masked_payload flows forward — never raw_payload
```

Masking tokens by type: `[CPF]`, `[CARD]` (L1); `[EMAIL]`, `[PHONE]`, `[IP]`, `[TOKEN]` (L2); `[UUID]` (L3)

**Writing unit tests for PII masking — use synthetic data only:**

```python
# CORRECT — synthetic placeholders
assert pii_filter.mask_dict({"email": "test@example.com"}) == {"email": "[EMAIL]"}
assert pii_filter.mask_dict({"cpf": "000.000.000-00"}) == {"cpf": "[CPF]"}

# NEVER use real PII in tests — it is a P1 security incident
```

---

## Using `prompt_injection_guard.py`

The guard detects structural patterns that indicate instruction-override attempts. On detection:

- Request is rejected immediately
- Only `sha256(input)[:16]` + rejection category is logged (never the raw input)
- `guardrail_injections_detected_total{category}` metric is incremented

**Writing unit tests — use synthetic placeholder tokens only:**

```python
# CORRECT — clearly synthetic
from src.guardrails.prompt_injection_guard import PromptInjectionGuard, RejectionReason

guard = PromptInjectionGuard()
result = guard.validate("SYNTHETIC_INJECT_ATTEMPT " * 60)
assert not result.is_valid
assert result.rejection_reason == RejectionReason.REPETITIVE_PATTERN

# Never use real exploit strings in test files
```

---

## Using `audit_logger.py`

Write-before-execute invariant: the audit record must be confirmed written **before** the action is dispatched. If the write fails, block the action.

```python
from src.guardrails.audit_logger import AuditLogger, AuditWriteError
from src.shared.models import AuditEvent

await audit_logger.log_event(
    AuditEvent(
        event_type="agent.action.proposed",
        agent_id=agent_id,
        action=action_type,
        outcome="PENDING",
        risk_score=score,
        metadata={
            "action_params_hash": sha256(str(masked_params)).hexdigest(),
            "guardrails_passed": ["pii_filter", "injection_guard", "action_limits"],
        },
        trace_id=trace_id,
    )
)
# Only after confirmed write — dispatch the action
```

If `audit_logger.log_event()` raises `AuditWriteError`, catch and block (do not swallow the exception).

---

## HITL Gateway Integration

Route to `src/agents/hitl_gateway.py` whenever:

- Risk score ≥ 0.4 (MEDIUM or HIGH tier)
- Action type is in the explicit HITL list in `specs/ai/hitl-hotl.md`

```python
if risk_score >= config.risk_threshold_hitl:
    decision = await hitl_gateway.request_approval(proposed_action)
    if decision.outcome != ApprovalOutcome.APPROVED:
        raise ActionRejectedError(decision.reason)
```

HITL timeout always rejects — never auto-approves on timeout. This is an inviolable rule.

---

## Checklist Before Merging Any Change to `src/guardrails/`

- [ ] All four guardrail layers still in the execution chain (none removed)
- [ ] Unit tests cover 100% of decision branches
- [ ] Tests use only synthetic placeholder tokens and fake data
- [ ] `test_pii_leakage.py` and `test_owasp_llm_top10.py` pass
- [ ] Security Lead has approved the PR (enforced by CODEOWNERS)
- [ ] No logging of raw input — only hash + category
- [ ] Failure mode defaults to REJECT, not pass-through
