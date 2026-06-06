# ADR-0052 — Agentic SDLC E2E Workflow

**Status:** Accepted (extended by ADR-0058)
**Date:** 2026-06-06
**Authors:** Valdomiro Souza

> **Extended by [ADR-0058](ADR-0058-agentic-spec-driven-delivery-workflow.md):** the
> model is now named the **Agentic Spec-Driven Delivery Workflow**, and the lifecycle
> evolved from 13 to 15 phases (0–14) — adding **Phase 0 Intake & Prioritization** and a
> conditional **Phase 10 AI Safety & Agent Governance**. The decisions in this ADR remain
> in force.

---

## Context

As AI agents become first-class participants in software delivery, the standard Git-flow + code-review cycle is insufficient. Agents can generate discovery artefacts, write specs, implement code, and propose deployments — but this creates governance gaps:

- No defined moment where human review is required for pre-code artefacts (discovery, NFR)
- No RACI clarity on who owns the Definition of Done at each layer
- No policy for when agent-generated docs bypass the runtime HITL gateway (appropriate) vs. when they must block through it (appropriate for actions with real-world effects)
- No standard for HITL governance of spec-phase artefacts vs. runtime agent actions
- No team-size-calibrated adoption path — the full governance stack is too heavy for a solo project

Six open questions from `agentic-sdlc-e2e-workflow-v2.md` drove this ADR:

| Question                                                   | Decision                                                                                                     |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Q1 — Who owns and enforces the Definition of Done?         | 3-tier RACI matrix; see `docs/process/RACI.md`                                                               |
| Q2 — How does HITL governance apply to pre-code artefacts? | Two-tier: Spec-as-PR (Tier 1) + Runtime gateway (Tier 2); see `docs/process/HITL-GOVERNANCE.md`              |
| Q3 — What tooling do we use for sprint tracking?           | GitHub Issues + GitHub Projects v2 (native); see `docs/process/SPRINT-TRACKING.md`                           |
| Q4 — How often do we run retrospectives?                   | Dual cadence: per-sprint (30 min async) + per-release (60–90 min); see `docs/process/RETROSPECTIVE-GUIDE.md` |
| Q5 — How do we gate model contract tests by LLM CI spend?  | Non-blocking budget circuit breaker; `scripts/check_llm_budget.py` + `ci-model-contract.yml`                 |
| Q6 — How does a new team adopt this progressively?         | Tier 0–4 adoption guide in `CUSTOMISING.md §8`                                                               |

---

## Decision

Adopt the **Agentic SDLC E2E Workflow** as a 13-phase lifecycle governing all feature development in this repository. The phases are:

| Phase | Name                | Primary Actor                   | Key Output                                          |
| ----- | ------------------- | ------------------------------- | --------------------------------------------------- |
| 1     | Conception          | Product Owner                   | GitHub Issue (feature_request template)             |
| 2     | Discovery           | Agent (draft) → Human (review)  | `docs/product/FEAT-{id}/discovery.md`, `nfr.md`     |
| 3     | Grooming            | Tech Lead                       | Issue reaches `status: ready`; DoR checklist passed |
| 4     | Specification       | Agent (draft) → Human (approve) | `specs/features/FEAT-{id}/feature-spec.md`          |
| 5     | Architecture        | Tech Lead                       | ADR filed if needed                                 |
| 6     | Development         | Developer / Agent               | Branch + implementation                             |
| 7     | Code Review         | Human + AI-assisted             | PR merged; DoD checklist satisfied                  |
| 8     | Testing             | CI + Developer                  | Unit ≥ 80%, integration, security, abuse cases      |
| 9     | DevSecOps           | CI + Security Lead              | SAST, SCA, Trivy, SBOM, DAST                        |
| 10    | Observability / PRR | SRE Lead                        | OTel spans, Prometheus metrics, PRR sign-off        |
| 11    | Release RC          | Release Manager                 | DoR-Release checklist; `rc-approved` label          |
| 12    | Production Deploy   | CD pipeline + SRE               | Canary 5% → 25% → 100%; GitHub Release tag          |
| 13    | Post-Deploy & Learn | Team                            | DORA metrics, retrospective, action items as Issues |

### Supporting artefacts introduced by this ADR

| Artefact                               | Path                                                   |
| -------------------------------------- | ------------------------------------------------------ |
| 13-phase workflow reference            | `docs/process/WORKFLOW.md`                             |
| RACI matrix (Q1)                       | `docs/process/RACI.md`                                 |
| HITL two-tier governance (Q2)          | `docs/process/HITL-GOVERNANCE.md`                      |
| Sprint tracking + team-size guide (Q3) | `docs/process/SPRINT-TRACKING.md`                      |
| Dual retrospective templates (Q4)      | `docs/process/RETROSPECTIVE-GUIDE.md`                  |
| Definition of Ready                    | `docs/process/DEFINITION_OF_READY.md`                  |
| Definition of Done                     | `docs/process/DEFINITION_OF_DONE.md`                   |
| Definition of Release                  | `docs/process/DEFINITION_OF_RELEASE.md`                |
| Feature spec template                  | `.github/FEATURE_SPEC_TEMPLATE.md`                     |
| Spike issue template                   | `.github/ISSUE_TEMPLATE/spike.md`                      |
| RFC discussion template                | `.github/DISCUSSION_TEMPLATE/rfc.md`                   |
| Discovery artefact governance          | `docs/product/README.md`                               |
| Budget circuit breaker (Q5)            | `scripts/check_llm_budget.py`, `ci-model-contract.yml` |
| Projects board definition              | `.github/project-board-definition.json`                |
| Issue lifecycle automation             | `.github/workflows/issue-lifecycle.yml`                |
| Progressive adoption guide (Q6)        | `CUSTOMISING.md §8`                                    |

### Governance decisions

**Q2 — Two-tier HITL governance:**

- Tier 1 (Spec-as-PR): discovery.md, nfr.md, feature-spec.md reviewed via GitHub PR — the PR review IS the HITL equivalent for pre-code phases. These documents do NOT pass through `src/agents/hitl_gateway.py`.
- Tier 2 (Runtime gateway): agent actions with real-world effects (API calls, DB writes, deployments) always route through `hitl_gateway.py`. This separation avoids blocking the spec workflow while preserving runtime safety.

**Q5 — Non-blocking budget circuit breaker:**

- When `LLM_CI_CURRENT_MONTH_SPEND_USD >= LLM_CI_MONTHLY_BUDGET_USD`, model contract tests are skipped and a PR comment is posted explaining why.
- The workflow still passes — this is a non-blocking gate. The Tech Lead acknowledges and the PR may be merged.
- Tests resume automatically next calendar month.

---

## Consequences

### Positive

- Every feature has a documented lifecycle from idea to post-deploy review
- Clear RACI eliminates ambiguity about who owns the DoD at each tier
- Spec-as-PR governance satisfies EU AI Act Article 13 transparency for agent-generated artefacts
- Progressive Tier 0–4 adoption means small teams get value without process overhead
- Budget circuit breaker prevents unexpected LLM CI spend spikes from blocking PRs

### Negative / Trade-offs

- Phase 1–5 pre-code workflow adds ~2–4h to feature start-up time (mitigated: agents do the initial drafting)
- Teams at Tier 0 must manually create the Projects board views (no CLI automation yet)
- The two-tier HITL separation requires explicit team training to avoid routing artefact reviews through the runtime gateway incorrectly

### Neutral

- Existing features in flight do not need to be back-filled through all 13 phases
- Per-service DoD addenda are optional — the global DoD is sufficient for most teams

## Alternatives Considered

**Single-tier HITL (all artefacts through runtime gateway):** Rejected — the gateway is designed for synchronous blocking of actions with real-world effects. Routing spec documents through it would create unnecessary blocking and add latency to the spec review cycle.

**External sprint tracker (Jira/Linear):** Rejected — creates a separate system of record. GitHub Issues + Projects keeps code, spec, and tracking in one system with native cross-linking and zero duplication.

**Single retrospective cadence (release only):** Rejected — release cadence is too infrequent to surface sprint-level friction in time to address it. The dual cadence catches small issues bi-weekly and provides a formal release-boundary review.
