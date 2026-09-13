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

<!-- Kept honest by scripts/governance/check_doc_consistency.py (C3): the highest ADR here must be the highest ADR on disk. Regenerate: the last 20 rows of docs/adr/README.md. -->

| ADR      | Decision                                          |
| -------- | ------------------------------------------------- |
| ADR-0070 | Governance gate enforcement lifecycle (report-mod… |
| ADR-0071 | Repository settings as code (branch protection co… |
| ADR-0072 | Versioned security control matrices (OWASP ASVS v… |
| ADR-0073 | SLO-driven canary thresholds (per-service config,… |
| ADR-0074 | Automated dependency & digest update policy (Reno… |
| ADR-0075 | Resilience fallback policy (degrade-open vs fail-… |
| ADR-0076 | Structured API error model (problem+json flavour)… |
| ADR-0077 | Idempotency keys for write endpoints (Idempotency… |
| ADR-0078 | List-endpoint pagination standard (offset/limit +… |
| ADR-0079 | Prompt externalisation (evaluator + orchestrator … |
| ADR-0080 | Groundedness scoring as an SLI (model-contract te… |
| ADR-0081 | RAG reference pipeline (chunk→embed→retrieve→rera… |
| ADR-0082 | Consolidated backup RPO/RTO + scheduled, evidence… |
| ADR-0083 | Rename `frontend/frontend` → `frontend/web` (refi… |
| ADR-0084 | Dependency & digest updates via Dependabot (super… |
| ADR-0085 | Unified spec identifier (SPEC-<DOMAIN>-NNN) and f… |
| ADR-0086 | HITL approval resumption (ApprovalConsumer execut… |
| ADR-0087 | Marker-based three-way template sync (.template-v… |
| ADR-0088 | Provider-neutral Terraform layering (partial back… |
| ADR-0089 | Documented-capability reachability as a tested in… |

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
