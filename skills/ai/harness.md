# Skill — Multi-Agent Harness Design

**Owner:** AI Lead | **Reviewer:** Tech Lead | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill when designing or implementing multi-agent harness patterns,
sprint contracts, context management strategies, or evaluator agents.

Spec: specs/ai/harness-design.md
ADR: ADR-0014 (Multi-Agent Harness Strategy)

---

## When to Use Each Mode

| Task complexity           | Harness mode | Agents active                   | Typical duration | Cost multiplier |
| ------------------------- | ------------ | ------------------------------- | ---------------- | --------------- |
| Simple, single-step       | `solo`       | Orchestrator P→R→A              | < 20 min         | 1×              |
| Feature-level, moderate   | `simplified` | Generator + Evaluator           | 30 min – 2 h     | ~5–10×          |
| Multi-feature, multi-hour | `full`       | Planner + Generator + Evaluator | 2–6 h            | ~15–25×         |

**Rule:** start with `solo`. Only escalate to `simplified` or `full` when you observe
quality plateau or context exhaustion on realistic problems. Harness overhead is only
justified beyond the solo capability boundary.

---

## Sprint Contract Checklist

Before any sprint begins, confirm the contract has:

- [ ] `objectives` written in user-experience language (no implementation details)
- [ ] `success_criteria` that are each independently testable
- [ ] Each criterion is binary: pass or fail — no "mostly works"
- [ ] No "and" clauses — split compound criteria into separate items
- [ ] Generator and Evaluator have both confirmed the contract before implementation

**Bad criterion:** "User can submit the form and it should mostly save correctly"
**Good criterion:** "Submitting a form with all required fields filled saves a record retrievable on the next page load"

---

## Evaluator Skepticism Rules

The Evaluator's system prompt must include explicit anti-leniency instructions.
Copy this block verbatim into any evaluator prompt:

```
Your DEFAULT assumption is that the implementation is INCOMPLETE or has DEFECTS.
Override this assumption only when you have actively confirmed correctness.

For each success criterion:
  - Test it independently. Do not infer from reading code alone.
  - "This looks correct" is NOT sufficient.
  - If you cannot confirm a criterion, it FAILS.
```

Never soften these rules. A lenient evaluator defeats the purpose of the harness.

---

## Context Reset Decision

Call `ContextManager.should_reset(utilisation)` at every inter-agent boundary.

```python
ctx_manager = ContextManager(reset_threshold=settings.harness_context_reset_threshold)

if ctx_manager.should_reset(current_utilisation):
    snapshot = ctx_manager.create_snapshot(
        agent_id=agent_id,
        task_id=task_id,
        masked_state=mask_dict(current_state),   # PII-mask BEFORE snapshot
        key_decisions=decisions_so_far,
        last_sprint_id=last_sprint_id,
    )
    resume_prompt = ctx_manager.restore_prompt(snapshot)
    # Inject resume_prompt as system message in the new context window
```

**Invariant:** `masked_state` passed to `create_snapshot()` must already be
PII-filtered. The caller is responsible — `ContextManager` applies a safety-net
pass but cannot guarantee the caller's intent.

---

## HITL Escalation Protocol

The harness escalates to HITL in two situations:

1. **Evaluator exhaustion:** after `harness_max_iterations` retries without passing.
2. **Planner spec review:** when `harness_planner_hitl_review = True` and task complexity is high.

Both escalations follow the write-before-execute invariant:

```python
# Audit BEFORE routing to HITL
await audit_logger.log_event(AuditEvent(
    action="harness_hitl_escalation",
    outcome="PENDING",
    metadata={"sprint_id": contract.sprint_id, "final_iteration": score.iteration},
))

# Then submit to HITL gateway
await hitl_gateway.submit_for_approval(request)
```

---

## Harness Simplification Principle

From Anthropic Engineering (2025):

> "Re-examine a harness, stripping away pieces that are no longer load-bearing."

Apply this principle regularly:

1. **After each model upgrade:** test whether the evaluator still adds value on your specific tasks.
2. **If simplified mode matches full mode quality:** disable the Planner (`harness_planner_enabled = False`).
3. **If solo mode matches simplified mode quality:** the task set has become simple enough for the P→R→A loop alone.

Use config flags to A/B test modes before permanently simplifying:

```bash
# Test solo vs simplified on the same task set
HARNESS_MODE=solo pytest tests/integration/test_harness_pipeline.py
HARNESS_MODE=simplified pytest tests/integration/test_harness_pipeline.py
```

---

## Common Mistakes

| Mistake                                                   | Consequence                                 | Fix                                      |
| --------------------------------------------------------- | ------------------------------------------- | ---------------------------------------- |
| Self-evaluating generator output                          | Self-praise bias; quality plateau           | Always use a separate EvaluatorAgent     |
| Success criteria with "and"                               | Criterion never clearly passes or fails     | One assertion per criterion              |
| Skipping audit log before HITL escalation                 | Compliance violation (write-before-execute) | Audit first, then submit                 |
| Passing unmasked state to `create_snapshot()`             | PII leak in context handoff                 | `mask_dict()` before `create_snapshot()` |
| Setting `harness_evaluator_enabled = False` in production | No quality gate                             | Only disable for debug sessions          |
