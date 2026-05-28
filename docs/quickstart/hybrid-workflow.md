# Hybrid Workflow: Vibe → Agêntico

> **Audience:** Engineers onboarding to the multi-agent harness  
> **Prerequisite:** [Python Backend quickstart](python-backend.md), [Contract-Driven Dev](contract-driven-dev.md)  
> **Related:** `specs/ai/harness-design.md`, `ADR-0017`, `skills/ai/harness.md`

---

## Overview

The hybrid workflow lets teams ship faster by blending **Vibe Mode** (rapid conversational iteration) with **Agêntico Mode** (autonomous, spec-driven multi-agent execution). Each phase has a clear entry condition, governance checkpoint, and exit gate.

```
┌──────────────┐     spec ready      ┌──────────────────┐
│  Phase 1     │────────────────────▶│  Phase 2          │
│  Vibe Mode   │                     │  Supervised Agent │
│  (explore)   │◀────────────────────│  (verify spec)    │
└──────────────┘    spec needs work  └──────────────────┘
                                              │
                                    HITL gate passed
                                              │
                                              ▼
                                     ┌──────────────────┐
                                     │  Phase 3          │
                                     │  Full Agentic     │
                                     │  (autonomous run) │
                                     └──────────────────┘
                                              │
                                     sprint complete
                                              │
                                              ▼
                                     ┌──────────────────┐
                                     │  Phase 4          │
                                     │  Review & Land    │
                                     │  (human closes)   │
                                     └──────────────────┘
```

---

## Phase 1 — Vibe Mode (Explore & Draft)

**When to use:** Problem is fuzzy. You need to explore options, draft a spec, or prototype quickly without governance overhead.

**What happens:**

- Claude Code assists conversationally. No HITL gateway invoked.
- Artefacts produced: rough spec draft, ADR draft, architecture sketch.
- No production changes. All output is in working files or `specs/` drafts.

**Exit gate:** A candidate spec exists in `specs/` with at least §1 Purpose, §2 Scope, and §3 Interface sections filled in.

**How to enter:** Type naturally. No special invocation needed.

---

## Phase 2 — Supervised Agentic (Verify Spec)

**When to use:** Spec draft is ready. You want the harness to validate it against existing ADRs, check for PII gaps, and propose a test plan — but with human confirmation at each step.

**What happens:**

- Harness `CoordinatorAgent` runs in `LOW_RISK` autonomy mode (see `src/shared/feature_flags.py`).
- Every action with real-world effects routes through `hitl_gateway.py`.
- `DecisionTreeLogger` records each branching decision to the audit log.
- Human approves or rejects at each HITL checkpoint via the review UI.

**Exit gate:** HITL approval received for the generated test plan and implementation outline. `ExecutionSummary` written to audit log.

**How to enter:**

```python
from src.agents.harness.coordinator import CoordinatorAgent
from src.agents.harness.models import SprintContract

contract = SprintContract(
    task_id="SPEC-NNN",
    spec_ref="specs/ai/your-spec.md",
    autonomy_level="LOW_RISK",
)
result = await CoordinatorAgent().run_sprint(contract)
```

---

## Phase 3 — Full Agentic (Autonomous Run)

**When to use:** Spec is approved, test plan is green, and governance has enabled `MEDIUM_RISK` or `FULL` autonomy for this task type.

**What happens:**

- Coordinator runs autonomously within the approved spec scope.
- HITL is triggered only when `risk_score` exceeds the action-type threshold.
- Self-reflection (`PatchProposal`) kicks in after `harness_patch_proposal_threshold` consecutive failures.
- All actions, decisions, and patch proposals written to the immutable audit log.

**Exit gate:** `EvaluatorScore.PASS` returned. `ExecutionSummary` attached to the sprint result.

**Governance requirement:** `autonomous-mode` feature flag must be enabled via ADR-0015 approval process. See `src/shared/feature_flags.py` and `infrastructure/feature-flags/`.

---

## Phase 4 — Review & Land (Human Closes)

**When to use:** Sprint produced a passing result. Human reviews output before merge.

**What happens:**

1. Review `ExecutionSummary` (decisions, iterations, patch proposals applied).
2. Check audit log for any anomalies (`action_type = "decision_bifurcation"` or `"sprint_execution_summary"`).
3. Run full test suite: `uv run pytest --cov=src --cov-fail-under=80`.
4. Open PR following branch conventions in `CLAUDE.md §6`.
5. PR checklist (`CLAUDE.md §7`) must pass before merge.

**Exit gate:** PR merged to `main`. CHANGELOG updated.

---

## Switching Between Phases

You can move backwards. If Phase 3 hits unexpected complexity, reduce autonomy level to `LOW_RISK` and resume in Phase 2 with human confirmation. The audit log preserves full history regardless of phase transitions.

| From → To   | Trigger                         | Action                                           |
| ----------- | ------------------------------- | ------------------------------------------------ |
| Phase 1 → 2 | Spec draft complete             | Set `autonomy_level = "LOW_RISK"`                |
| Phase 2 → 3 | HITL approval + governance flag | Set `autonomy_level = "MEDIUM_RISK"` or `"FULL"` |
| Phase 3 → 2 | Unexpected risk or spec gap     | Reduce `autonomy_level`, re-enter HITL loop      |
| Any → 4     | Sprint passes                   | Open PR, human reviews                           |

---

## Common Mistakes

| Mistake                                         | Fix                                                              |
| ----------------------------------------------- | ---------------------------------------------------------------- |
| Skipping Phase 2 and going straight to Phase 3  | Always get HITL approval on the implementation plan first        |
| Using `FULL` autonomy without ADR-0015 approval | Governance review required — see `docs/ai-governance/`           |
| Not checking `ExecutionSummary` before merging  | Always read the summary; patch proposals indicate spec ambiguity |
| Committing directly to `main`                   | Follow branch conventions: `feature/SPEC-NNN-description`        |
