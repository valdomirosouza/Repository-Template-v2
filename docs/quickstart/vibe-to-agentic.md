# Quickstart — From Vibe Coding to Full Agentic

> **Audience:** Engineers joining the team with a vibe-coding background — comfortable
> prompting LLMs conversationally, new to supervised multi-agent workflows.  
> **Prerequisite:** [Python Backend quickstart](python-backend.md)  
> **Related:** [Hybrid Workflow guide](hybrid-workflow.md), `CLAUDE.md §9`

---

## Why this guide exists

Vibe coding (rapid, conversational LLM use) has a low entry barrier. The agentic
harness in this repo has a moderate learning curve — you need to understand how to
supervise, intervene in, and configure agent behaviour. This guide bridges that gap
in three progressive levels, each designed to be reached within the timeframe shown.

> **Risk to watch:** Over-relying on agents for routine tasks can erode your grasp of
> core programming concepts. The mandatory SDD cycle (specs before code) exists
> precisely to keep engineers in the loop — you must understand what the agent is
> building before it builds it.

---

## Level 1 — Vibe Mode (day one)

**Goal:** Use Claude Code to explore, document, and test the codebase — without
triggering the agentic harness at all.

### What is safe to do on day one

| Task                               | How                                                          |
| ---------------------------------- | ------------------------------------------------------------ |
| Explore unfamiliar files           | `Read` tool or ask Claude Code in plain language             |
| Generate docstrings                | Ask Claude Code to document a function you select            |
| Write unit tests for existing code | Ask Claude Code to add tests for a specific module           |
| Understand a spec                  | Ask Claude Code to explain `specs/ai/harness-design.md`      |
| Read audit logs                    | Ask Claude Code to summarise recent entries in `guardrails/` |

### Prompts that are safe at Level 1

```
"Explain what src/agents/harness/coordinator.py does."
"Write unit tests for src/memory/session_memory.py — no new behaviour, just tests."
"Show me how the PII filter works in src/guardrails/pii_filter.py."
"Summarise the decisions in docs/adr/ADR-0014-multi-agent-harness-strategy.md."
```

### What Level 1 does NOT do

- Does not call `HarnessCoordinator.run()` or any agent pipeline.
- Does not write to production files without your explicit review.
- Does not route anything through `hitl_gateway.py`.

### Level 1 boundary — when to stop and escalate

If your task requires the agent to **create new files**, **modify existing source code**,
or **call an external API**, move to Level 2. Vibe Mode is purely exploratory.

---

## Level 2 — Supervised Agentic (first week)

**Goal:** Submit a task to the harness with HITL mandatory at every consequential step.
Learn to read `ExecutionSummary` and `EvaluatorScore`.

### Set up your first supervised run

```python
from src.agents.harness.coordinator import HarnessCoordinator
from src.agents.harness.models import TaskBrief

brief = TaskBrief(
    task_id="SPEC-NNN",           # must match a GitHub issue with a linked spec
    description="Add input validation to the /api/v1/requests endpoint.",
    complexity="low",
    trace_id="my-trace-001",
    correlation_id="corr-001",    # ties all audit events together
)

# Run with LOW_RISK — every consequential action gets a HITL checkpoint
result = await coordinator.run(brief)
```

The harness will pause at every action and wait for your approval in the review UI
before proceeding. Nothing executes without your explicit sign-off.

### Reading an EvaluatorScore

After each sprint iteration the evaluator scores the generator's output on four
dimensions (0.0–1.0 each):

| Field           | What it measures                                          |
| --------------- | --------------------------------------------------------- |
| `quality`       | Correctness relative to the success criteria              |
| `originality`   | Avoidance of copy-paste or trivial solutions              |
| `craft`         | Code style, naming, type safety                           |
| `functionality` | Does it actually work end-to-end?                         |
| `passed`        | `True` only when `average ≥ pass_threshold` (default 0.7) |

```python
score = result.final_score
print(f"Average: {score.average:.2f}  Passed: {score.passed}")
print(f"Feedback: {score.feedback}")
```

If `passed` is `False` the harness retries automatically (up to `harness_max_iterations`).

### Reading an ExecutionSummary

The `ExecutionSummary` is written to the audit log at the end of every sprint — pass
or escalation. Find it with:

```bash
# In the audit log (InMemoryAuditStorage in tests; Postgres in staging/prod)
# action = "sprint_execution_summary"
```

Key fields:

| Field                     | Meaning                                                             |
| ------------------------- | ------------------------------------------------------------------- |
| `total_iterations`        | How many generate→evaluate cycles ran                               |
| `failures`                | List of failure reasons per iteration (first 100 chars of feedback) |
| `patch_proposals_applied` | Times self-reflection generated a `PatchProposal`                   |
| `decisions`               | List of `DecisionPoint` objects — every branching decision logged   |
| `final_score`             | The last `EvaluatorScore`                                           |

If `patch_proposals_applied > 0` the spec likely has an ambiguity — review it before
the next run.

### HITL checkpoints at Level 2

Every time the coordinator calls `hitl_gateway.submit_for_approval()` you will see a
pending request in the review UI. You can:

- **Approve** — agent proceeds with the proposed action.
- **Reject** — agent records the rejection in `BugHistoryStore` and retries or escalates.
- **Let it expire** — always results in `EXPIRED_AUTO_REJECTED`; never auto-approval (ADR-0011).

### Level 2 boundary — when to move up

You are ready for Level 3 when you can answer yes to all of these:

- [ ] I can read an `EvaluatorScore` and understand why it passed or failed.
- [ ] I can read an `ExecutionSummary` and trace every decision the agent made.
- [ ] I have approved and rejected at least one HITL request intentionally.
- [ ] I understand what `harness_patch_proposal_threshold` does and when it fires.

---

## Level 3 — Full Agentic (first month)

**Goal:** Configure autonomy levels per action type, interpret agent failures from
logs, and tune `risk_score` thresholds for your context.

### Configuring autonomy levels

Autonomy is controlled by the `autonomous-mode` OpenFeature flag (ADR-0015).
**Never enable `FULL` autonomy without explicit governance sign-off.**

```python
from src.shared.feature_flags import get_autonomy_level, AutonomyLevel

# Check what autonomy level applies to a given action at a given risk score
level = get_autonomy_level(action_type="write_file", risk_score=0.4)
# → AutonomyLevel.LOW_RISK  (human approval still required)

level = get_autonomy_level(action_type="read_file", risk_score=0.1)
# → AutonomyLevel.MEDIUM_RISK  (threshold-based, no approval for low-risk reads)
```

Autonomy levels from least to most permissive:

| Level         | What the agent can do autonomously                            |
| ------------- | ------------------------------------------------------------- |
| `READ_ONLY`   | Read files and specs only                                     |
| `TESTS_ONLY`  | Run tests, read; no writes                                    |
| `LOW_RISK`    | Writes + reads; every action needs HITL approval              |
| `MEDIUM_RISK` | Writes + reads; HITL only above the per-action-type threshold |
| `FULL`        | No HITL unless the action explicitly requires it              |

### Interpreting agent failures from logs

When a sprint fails, look for these audit event sequences:

```
event_type = "agent.decision.bifurcation"   → DecisionPoint logged
event_type = "agent.action.executed"        → action ran (check outcome)
event_type = "agent.action.proposed"        → HITL pending
action     = "sprint_execution_summary"     → full sprint history
```

A pattern of `decision_bifurcation` followed immediately by `sprint_execution_summary`
with `total_iterations = harness_max_iterations` means the agent hit max retries —
**the spec is likely ambiguous**. Clarify the success criteria before re-running.

If `patch_proposals_applied ≥ 2` across consecutive sprints for the same task, escalate
to the Tech Lead — the spec may need a formal revision.

### Tuning risk_score thresholds

The feedback loop (`src/agents/feedback_loop.py`) adjusts the `risk_score` bias for
each `action_type` based on the HITL rejection rate over a rolling window. You can
also set manual overrides in `src/shared/config.py`:

```python
# pyproject.toml or environment variables
FEEDBACK_REJECTION_WINDOW_DAYS=7
FEEDBACK_BIAS_STEP=0.05
FEEDBACK_MAX_BIAS=0.5
```

A high `agent_feedback_rejection_rate` gauge for `deploy` means the agent consistently
proposes deployments that humans reject — raise the threshold or tighten the spec.
Watch the Grafana dashboard: `infrastructure/monitoring/grafana/dashboards/agent-feedback-loop.json`.

### Monitoring autonomous runs

Use the Agent Performance dashboard for MTTD/MTTR visibility:
`infrastructure/monitoring/grafana/dashboards/agent-performance.json`

SLO targets to track:

| Signal                     | Target          |
| -------------------------- | --------------- |
| MTTD p99                   | ≤ 60 s          |
| MTTR p99                   | ≤ 600 s         |
| Autonomous resolution rate | ≥ 80%           |
| Cost per resolution p99    | ≤ 10 000 tokens |

If `agent_autonomous_resolution_rate` drops below 0.8 for a sustained period, check:

1. `harness_max_iterations` — may need increasing for complex tasks.
2. `harness_evaluator_pass_threshold` — may be set too high.
3. Spec quality — success criteria must be independently testable and binary.

---

## Summary: progression at a glance

```
Day 1 ──────── Week 1 ──────── Month 1
  │                │               │
Vibe Mode   Supervised       Full Agentic
  │          Agentic              │
  │             │                 │
Read, explore  HITL on every    Configure autonomy
Document       step             Tune thresholds
Write tests    Read summaries   Monitor SLOs
               Approve/reject   Diagnose failures
```

The SDD cycle is mandatory at every level. Specs come before code — always.

---

## What to read next

| Topic                                    | Where                                                                          |
| ---------------------------------------- | ------------------------------------------------------------------------------ |
| 4-phase hybrid workflow (full reference) | `docs/quickstart/hybrid-workflow.md`                                           |
| Harness spec                             | `specs/ai/harness-design.md`                                                   |
| HITL governance                          | `docs/ai-governance/` + ADR-0011, ADR-0015, ADR-0016                           |
| Agent memory                             | `specs/ai/agent-memory.md` + ADR-0017                                          |
| Observability                            | `skills/sre/golden-signals.md`, `skills/observability/otel-instrumentation.md` |
| PII rules                                | `skills/privacy/pii.md`, `docs/privacy/pii-inventory.md`                       |
