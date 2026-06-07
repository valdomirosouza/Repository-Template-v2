# Agentic Spec-Driven Delivery — Claude Code Agents

A multi-agent system that **operates** the 15-phase
[Agentic Spec-Driven Delivery Workflow](../../docs/sdlc/agentic-spec-driven-delivery.md)
inside Claude Code: one **orchestrator** sequences **15 phase agents** (Phase 0–14).
Each agent owns exactly one phase, validates its inputs, produces a persisted artifact,
and emits a structured **handoff** (see
[`docs/sdlc/agent-handoff-schema.md`](../../docs/sdlc/agent-handoff-schema.md)).

> **Dev-time vs. runtime.** These `.claude/agents/` subagents run via the Claude Code
> CLI to _drive delivery_. They are **distinct** from the runtime product agents in
> `src/agents/` (the deployed app's HITL/HOTL orchestrator, guardrails, tool registry).

## Roster

| Agent                         | Phase | Owns                                                                                                                                    |
| ----------------------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `asdd-orchestrator`           | —     | Sequences 0→14, retries on `blocked`, stops at human gates, final report                                                                |
| `asdd-phase-0-intake`         | 0     | Intake & Prioritization (problem, value, risk class, owner)                                                                             |
| `asdd-phase-1-conception`     | 1     | GitHub Issue (feature_request)                                                                                                          |
| `asdd-phase-2-discovery`      | 2     | discovery.md + nfr.md (Spec-as-PR)                                                                                                      |
| `asdd-phase-3-grooming`       | 3     | DoR checklist; Issue → ready                                                                                                            |
| `asdd-phase-4-specification`  | 4     | feature-spec.md (Spec-as-PR)                                                                                                            |
| `asdd-phase-5-architecture`   | 5     | ADR (if needed) + threat model                                                                                                          |
| `asdd-phase-6-development`    | 6     | Implementation branch, lint + unit tests                                                                                                |
| `asdd-phase-7-code-review`    | 7     | PR, DoD, CI gates (human approval)                                                                                                      |
| `asdd-phase-8-testing`        | 8     | Unit ≥80% + integration + security + abuse cases                                                                                        |
| `asdd-phase-9-devsecops`      | 9     | SAST/SCA/Trivy/SBOM/DAST                                                                                                                |
| `asdd-phase-10-ai-safety`     | 10    | Injection/leakage tests, tool-permission review (AI/agent only)                                                                         |
| `asdd-phase-11-observability` | 11    | OTel/metrics verified; PRR sign-off                                                                                                     |
| `asdd-phase-12-release-rc`    | 12    | DoR-Release; rc-approved (human-gated)                                                                                                  |
| `asdd-phase-13-production`    | 13    | Canary plan + GitHub Release (human-executed)                                                                                           |
| `asdd-phase-14-post-deploy`   | 14    | DORA metrics + retrospectives                                                                                                           |
| `phase-executor`              | any   | Generic single-phase dry-run executor used by the `/deliver` skill (reads only its phase's ADRs/specs/guardrails; no real side-effects) |

## Running it

Two entrypoints share these phase contracts:

- **`asdd-orchestrator`** — the full production-grade workflow (real Issues/PRs, stops at the
  nine human gates). Use for actual delivery.
- **`/deliver <spec>`** skill (`.claude/skills/deliver/`) — a **dry-run** orchestrator that
  drives one spec through all 15 phases via the `phase-executor` subagent and emits a
  `reports/<slug>/FINAL-REPORT.md` (traceability + timing + speedup). No real side-effects.

```text
1. Invoke `asdd-orchestrator` with the feature request.
2. It runs `scripts/asdd_state.py init` to create shared state.
3. It invokes each phase agent in order via the Agent tool, passing the feature id.
4. Each phase agent appends a handoff (scripts/asdd_state.py append-handoff).
5. On `blocked` → the orchestrator retries (bounded) or surfaces the reason and halts.
6. On `human_gate: true` → the orchestrator stops for explicit human approval.
7. After Phase 14 → the orchestrator emits the final delivery report.
```

## Skills

Each phase agent declares a `## Skills — load before executing` section binding the
relevant repo skill(s) for its domain (e.g. Phase 8 → `engineering/testing-strategy` +
`devsecops/owasp-top10`; Phase 10 → `ai/guardrails` + `ethics/ethical-ai-review`). Because
each subagent runs in its own context, it loads those skills itself rather than inheriting
the main session's. Bindings respect the ≤ 2-skills-per-task budget (CLAUDE.md §4, §13.2).

## Governance

Agents **recommend and prepare; humans approve, own, operate.** They validate inputs
first (`blocked` + `reason` + halt on failure), stop at the nine mandatory human gates,
and never autonomously merge, deploy, cut releases, or change autonomy flags
(CLAUDE.md §3.3, ADR-0011/0053/0058). The Release and Production agents produce the
plan and readiness verdict; a human executes the irreversible step.
