# `/deliver` — example dry-run output (SPEC-LGS-001)

These files are an **illustrative, committed example** of what the [`/deliver`](../../../.claude/skills/deliver/SKILL.md)
skill produces when it drives a spec through the 15-phase Agentic Spec-Driven Delivery workflow
(ADR-0058) as a **governed dry-run** (no real side-effects).

> **Provenance.** Archived from a real `/deliver dry-run` of
> [`specs/system/SPEC-LGS-001-log-based-golden-signals.md`](../../../specs/system/SPEC-LGS-001-log-based-golden-signals.md)
> on **2026-06-08** using the two-mode (`dry-run | code`) skill. All 15 phases ran via the
> `phase-executor` subagent with real validation evidence (`make lint-python`, `make
test-unit-python` → 945 tests / 86.56% coverage, `make check-control-bindings`). Gate verdicts
> include the real `BLOCKED` / `SIMULATED` / `N-A` states, and every consequential step resolved to
> a human gate rather than auto-executing. The run also surfaced process findings tracked in
> [`../deliver-dryrun-findings.md`](../deliver-dryrun-findings.md).

Normally `/deliver` writes to `reports/<slug>/` (gitignored). This folder pins the three
human-readable outputs from that run:

| File                                 | What it is                                                                                         |
| ------------------------------------ | -------------------------------------------------------------------------------------------------- |
| [`00-plan.md`](00-plan.md)           | Phase-0 plan: problem, risk class, 15-phase plan, evidence strategy                                |
| [`backlog.yaml`](backlog.yaml)       | Decomposed backlog (id, phase, depends_on, adr_refs, acceptance, t-shirt)                          |
| [`FINAL-REPORT.md`](FINAL-REPORT.md) | Gate results · requirement-traceability · task/timing/speedup · evidence appendix · open-HITL list |

The per-phase `artifacts/` and `logs/` of a run are **not** committed (they live under the
gitignored `reports/` tree). This is a snapshot, not a live report — re-run `/deliver` for current results.
