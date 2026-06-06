# AI Safety & Agent Governance Checklist

> **Gate:** Phase 10 of the [Agentic Spec-Driven Delivery Workflow](../sdlc/agentic-spec-driven-delivery.md).
> **Conditional:** required for **AI, LLM, or agentic** features — any change under
> `src/agents/` or `src/guardrails/`, a new `action_type`, or an autonomy change.
> Skipped for non-AI changes (risk-based flow).
> **Approver:** AI Governance Lead (+ Security Lead for high/critical findings).
> **ADR:** ADR-0058, ADR-0053, ADR-0015, ADR-0011.

Complete this checklist before an AI/agent feature passes Phase 10. Attach it to the
PR (or link a completed copy). Each item maps to enforcement that already exists in
this repository — link the evidence (test, audit record, config) rather than
re-describing it.

```markdown
## AI Safety & Agent Governance Checklist

- [ ] **Agent purpose and boundaries documented** — scope_boundary + `allowed_action_types`
      declared in the feature spec and enforced by `SpecContractEnforcer` (ADR-0047).
- [ ] **Tool permissions explicitly defined** — every tool the agent may call is registered
      in `infrastructure/agent-tools/tools.yaml` with risk level, `requires_hitl`,
      `execution_mode`, rate limits, and reversibility metadata (ADR-0048/0055).
      Unregistered tools are blocked by `ToolExecutor` (ADR-0053).
- [ ] **HITL required for irreversible / high-risk actions** — mandatory-HITL categories
      route through `src/agents/hitl_gateway.py`; `action_policy.requires_mandatory_hitl`
      cannot be downgraded by a numeric score (ADR-0053).
- [ ] **Prompt-injection risks tested** — `prompt_injection_guard` on; jailbreak/goal-hijack
      cases in `tests/abuse_cases/` cover this feature (count must not decrease, ADR-0050).
- [ ] **Sensitive-data exposure tested** — PII non-leakage covered by
      `tests/security/test_pii_leakage.py` and/or `tests/model_contract/`.
- [ ] **Model inputs/outputs logged safely** — `pii_filter.mask_*` runs before every LLM
      call and every log write; LLM output sanitized before render/exec (LLM02/LLM06).
- [ ] **PII handling compliant** — new PII surface flagged for DPIA/RIPD; classified L1–L4
      in `docs/privacy/pii-inventory.md`.
- [ ] **Evaluation dataset / test cases documented** — risk-calibration and/or
      model-contract scenarios exist and pass (`tests/unit/agents/test_risk_calibration.py`,
      `tests/model_contract/`, ADR-0051/0054).
- [ ] **Failure modes documented** — degraded-mode behaviour (LLM/Redis/Kafka/DB down) and
      the in-memory fallbacks are described; HOTL compensation/override defined where
      applicable (ADR-0055).
- [ ] **Cost, timeout, and rate-limit controls defined** — per-tool rate limits in
      `tools.yaml`; LLM token budget + circuit breaker configured (`src/shared/config.py`).
- [ ] **Model / version dependencies recorded** — model id pinned in
      `docs/dependency-manifest.yaml`; model-contract tests run before any promotion (ADR-0051).
- [ ] **Audit trail available** — every agent action is logged immutably via
      `guardrails/audit_logger.py` with `request_id`/`trace_id`.
- [ ] **Autonomy level appropriate** — the action's autonomy ceiling and oversight mode
      (HITL/HOTL) are correct for its risk; enabling `FULL` requires ADR-0015 sign-off.
```

---

## How this gate is enforced

| Concern                      | Enforced by                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------ |
| Prompt injection             | `src/guardrails/prompt_injection_guard.py`, `tests/abuse_cases/`                     |
| Tool permissions             | `src/agents/tool_registry.py` + `tools.yaml`, `ToolExecutor` (ADR-0053)              |
| HITL / autonomy              | `src/agents/hitl_gateway.py`, `action_policy.py`, feature flags (ADR-0011/0015/0053) |
| Reversibility / compensation | `compensation_registry.py`, `override_service.py` (ADR-0055)                         |
| PII / data leakage           | `src/guardrails/pii_filter.py`, `tests/security/test_pii_leakage.py`                 |
| Model behaviour              | `tests/model_contract/`, `docs/dependency-manifest.yaml` (ADR-0051)                  |
| Auditability                 | `src/guardrails/audit_logger.py`                                                     |
| Behavioural drift            | `src/agents/behavioral_monitor.py`, `runtime_policy_gateway.py` (ADR-0049)           |

See also: [`skills/ai/guardrails.md`](../../skills/ai/guardrails.md),
[`docs/process/HITL-GOVERNANCE.md`](../process/HITL-GOVERNANCE.md), and the OWASP LLM
Top-10 controls in `CLAUDE.md §3.2`.
