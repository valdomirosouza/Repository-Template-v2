# Claude Code Session Primer

> Auto-loaded at session start. Supplements `CLAUDE.md` and `skills/sdlc/agent-onboarding.md`.
> Keep this file concise — it is loaded into every session's context window.

---

## Repo Identity

- **Repo:** Repository-Template-v2
- **Type:** Multi-language enterprise monorepo template (Python/FastAPI, Java/Spring Boot, Go, Next.js)
- **Current version:** see `version.txt`
- **Active branch convention:** `develop` for work-in-progress; `main` for releases

## Critical Paths (highest sensitivity — escalate before touching)

| Path                            | Why sensitive                           |
| ------------------------------- | --------------------------------------- |
| `src/agents/hitl_gateway.py`    | Dual-approval: Security + AI Governance |
| `src/guardrails/`               | Security Lead approval required         |
| `src/shared/feature_flags.py`   | Controls HITL/HOTL autonomy — ADR-0015  |
| `infrastructure/feature-flags/` | Governance review required              |
| `.github/workflows/`            | DevOps Lead ownership                   |

## Open Work

Check current open issues before starting:

```bash
gh issue list --repo valdomirosouza/Repository-Template-v2 --state open --label agentic-sdlc
```

Wave labels: `wave-1` (done) → `wave-2` → `wave-3` → `wave-4` → `wave-5`

## Task Atomicity Kickoff (ADR-0060, CLAUDE.md §4)

> Decompose this work so that **no task needs more than 2 repo skills** to finish.
> Treat the 2-skill budget as the _test_ for whether a task is atomic: if a task would
> need a 3rd skill, **split it at that boundary** instead of loading the skill. Each task
> produces **exactly one reviewable artifact** and declares its ≤ 2 bindings under
> `## Skills — load before executing`. `CLAUDE.md` and repo context do **not** count toward
> the budget. Before closing each Agentic SDLC phase, list the artifacts the phase owes and
> create a dedicated atomic task for any that is missing. Run the cross-cutting control
> triggers (`docs/governance/control-applicability-matrix.md`) before every task.

## Session Bootstrap Checklist

- [ ] CLAUDE.md read and §14 escalation triggers noted
- [ ] `services.yaml` scanned for affected service
- [ ] Work decomposed so each task needs ≤ 2 skills and yields one artifact (ADR-0060)
- [ ] Relevant skill(s) loaded (max 2)
- [ ] Cross-cutting control triggers checked (control-applicability-matrix)
- [ ] GitHub Issue identified with spec reference
- [ ] Spec status confirmed as `Approved`

## ADR Quick Index (most recent)

| ADR      | Decision                                          |
| -------- | ------------------------------------------------- |
| ADR-0031 | Agent onboarding protocol                         |
| ADR-0032 | Sub-agent specialization registry                 |
| ADR-0033 | Long-running agent session durability             |
| ADR-0034 | Agentic escalation protocol                       |
| ADR-0035 | AI-assisted CI review                             |
| ADR-0036 | Agentic cyber defense protocol                    |
| ADR-0037 | Governance gate enforcement                       |
| ADR-0038 | Learn stage feedback loop                         |
| ADR-0039 | Governed tool registry                            |
| ADR-0040 | Agentic maturity self-assessment                  |
| ADR-0041 | Context graph — autonomy tier                     |
| ADR-0042 | Kubernetes probe strategy                         |
| ADR-0043 | OTel Collector OTTL PII redaction + tail sampling |
| ADR-0044 | OTel agent span hierarchy                         |
| ADR-0045 | GenAI semantic conventions for LLM                |
| ADR-0046 | HITL trace linking + guardrail events             |
| ADR-0047 | Spec contract enforcement at runtime              |
| ADR-0048 | Zero-trust tool registry + operator auth          |
| ADR-0049 | Runtime behavioral monitoring                     |
| ADR-0050 | Adversarial abuse testing strategy                |
| ADR-0051 | Model behavioral contracts (MLSecOps)             |
| ADR-0052 | Agentic SDLC E2E workflow (origin)                |
| ADR-0058 | Agentic Spec-Driven Delivery (15-phase, 0–14)     |

Full index: `docs/adr/README.md`

## Process Quick Reference (ADR-0052)

| Document                   | Path                                        | Use when                               |
| -------------------------- | ------------------------------------------- | -------------------------------------- |
| Delivery model (canonical) | `docs/sdlc/agentic-spec-driven-delivery.md` | Understand the workflow + positioning  |
| Phase lifecycle            | `docs/process/WORKFLOW.md`                  | Any feature task — check current phase |
| HITL governance            | `docs/process/HITL-GOVERNANCE.md`           | Creating discovery/spec artefacts      |
| Definition of Ready        | `docs/process/DEFINITION_OF_READY.md`       | Grooming ceremony / sprint entry       |
| Definition of Done         | `docs/process/DEFINITION_OF_DONE.md`        | PR checklist                           |
| Definition of Release      | `docs/process/DEFINITION_OF_RELEASE.md`     | Release candidate review               |
| RACI matrix                | `docs/process/RACI.md`                      | Unclear ownership question             |
| Sprint tracking            | `docs/process/SPRINT-TRACKING.md`           | Projects board, label taxonomy         |
| Retrospective guide        | `docs/process/RETROSPECTIVE-GUIDE.md`       | Sprint or release retrospective        |
