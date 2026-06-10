# Per-Phase Context Budget

> **Status:** Active | **Owner:** Tech Lead | **ADR:** ADR-0058 (lifecycle), ADR-0060 (ambient
> context never occupies a skill slot) | **Companion:** `CLAUDE.md §13` (Context & Token Efficiency)

Makes each phase's context **deterministic and measurable**: what a phase-executor loads by
default (`base_load`), what it pulls only when the work references it (`on_demand`), and a soft
**token ceiling** per phase. This is the lifecycle companion to the 2-skill budget (ADR-0060) —
the skill budget caps _domain skills_; this caps _documents_. The authoritative machine pointer is
`docs/process/gates/phase-gates.yaml › context_budget_ref`.

## Enforcement status (read this first)

This budget is **advisory and reviewed, not proxy-enforced.** The RTK token-filter proxy was
removed (ADR-0030, deprecated 2026-06-07; guidance retained in `CLAUDE.md §13`), so there is no
`.rtk/filters.toml` to enforce it mechanically today. It is enforced by:

- the `/deliver` orchestrator and `phase-executor` briefing only the `base_load` for a phase and
  fetching `on_demand` docs lazily (the orchestrator is deliberately _thin_; `.claude/skills/deliver/SKILL.md`);
- review of the FINAL-REPORT's per-phase evidence;
- the OTel/golden-signals telemetry that already measures agent context size.

If an RTK-style proxy is reintroduced, this table is the source it should compile its filters from.

## Ambient context (never counted — ADR-0060)

`CLAUDE.md`, `AGENTS.md`, repo structure, `services.yaml`, `docs/process/gates/phase-gates.yaml`,
and already-accepted ADRs/specs ride along in **every** phase and never count against a budget.
Budgets below govern the _task-specific_ documents a phase loads on top of that ambient base.

## Targets

Whole-window target: keep loaded context **< 40k tokens (~20% of a 200k window)**, reserving
**160k+** for reasoning and output (mirrors the figures in
`spec-driven-insights-for-repository-template-v2.md §3.2`). The per-phase `token_ceiling` is the
soft cap on `base_load + the on_demand actually pulled`.

| Phase                      | base_load (always)                                             | on_demand (only if referenced)                 | token_ceiling |
| -------------------------- | -------------------------------------------------------------- | ---------------------------------------------- | ------------- |
| 0 Intake                   | the request/issue                                              | related specs/ADRs surfaced for risk-class     | 8k            |
| 1 Conception               | discovery template                                             | prior FEAT discovery docs                      | 12k           |
| 2 Discovery                | the spec §1–§6, `skills/privacy/pii.md`                        | `docs/privacy/pii-inventory.md`, threat-model  | 20k           |
| 3 Grooming                 | the spec, `docs/process/DEFINITION_OF_READY.md`                | `skills/sdlc/spec-lifecycle.md`                | 16k           |
| 4 Specification            | the spec, `specs/SPEC-TEMPLATE.md`, ≤2 domain skills           | related specs in `related_specs`               | 24k           |
| 5 Architecture             | the spec §7/§14, `docs/adr/README.md`                          | the specific reused ADRs; threat-model         | 20k           |
| 6 Development              | the spec section in scope, ≤2 domain skills                    | the interface contract, the data-model section | 32k           |
| 7 Code Review              | the diff, the spec acceptance criteria                         | `CLAUDE.md §7`, governance labels doc          | 24k           |
| 8 Testing                  | the diff, `skills/engineering/testing-strategy.md`             | `tests/` fixtures, abuse-case suite            | 24k           |
| 9 Security & DevSecOps     | the diff, `skills/devsecops/pipeline-security.md`              | `.github/control-triggers.yml`, SBOM           | 20k           |
| 10 AI Safety (conditional) | `skills/ai/guardrails.md`, the spec `allowed_action_types`     | abuse-case suite, `docs/ai-governance/`        | 24k           |
| 11 Observability           | the spec §10, `skills/sre/golden-signals.md`                   | runbook template, `docs/sre/slo/slo.yaml`      | 16k           |
| 12 Release Candidate       | `version.txt`, `CHANGELOG.md`                                  | `docs/process/DEFINITION_OF_RELEASE.md`        | 12k           |
| 13 Production Deployment   | the deploy plan, `skills/change-management/deploy-rollback.md` | `docs/change-log/`, CAB record                 | 12k           |
| 14 Post-Deployment & Learn | DORA dashboard refs, retrospective template                    | prior retrospectives                           | 12k           |

**Never load simultaneously:** the full ADR corpus, every skill file, or unrelated FEAT specs —
load the _specific_ ADR/skill/spec a phase names, never the directory. Right-sizing tiers
(ADR-0064) further reduce which phases run at all, shrinking total context for low tiers.

## How `/deliver` honours this

The orchestrator briefs the `phase-executor` with the `base_load` for phase N and instructs it to
fetch `on_demand` docs only when the task references them — matching the narrow receive-envelope in
`docs/sdlc/agent-handoff-schema.md`. The per-phase ceiling is recorded in the FINAL-REPORT's
evidence so context growth is observable.
