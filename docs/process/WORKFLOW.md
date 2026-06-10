# Agentic SDLC End-to-End Workflow

> **Version:** 2.0.0 | **Last updated:** 2026-06-06
> **Status:** Active | **Owner:** Tech Lead
> **Source:** `agentic-sdlc-e2e-workflow-v2.md` + `agentic-sdlc-documentation-recommendation.md`
> **ADR:** ADR-0052, ADR-0058

This is the living, operational workflow reference for this repository — the detailed
per-phase companion to the canonical model in
[`docs/sdlc/agentic-spec-driven-delivery.md`](../sdlc/agentic-spec-driven-delivery.md).
It maps the agent pathway (Perceive → Reason → Act → Learn) across the **15-phase
(0–14)** risk-based lifecycle. The lifecycle is adaptive: low-risk changes take a
short path (see the Risk-Based Flow in the canonical reference); only high-impact
changes pass every gate.

**Notation:** ◈ = Human governance checkpoint | ⚡ = Agent-accelerated step

---

## Delivery Right-Sizing Tiers (ADR-0064)

The 15 phases below are the **full** lifecycle. How many of them a given change actually runs is
set by its **delivery tier** — the scope axis of `/deliver` (`/deliver [dry-run|code] [tier]
[language] <spec>`), alongside mode and language. This is the lifecycle dual of the 2-skill
budget (ADR-0060): _not every spec deserves every phase_.

| Tier        | Runs                                                                                           |
| ----------- | ---------------------------------------------------------------------------------------------- |
| `TRIVIAL`   | Control phases + a lightweight spec; process phases (Conception, Grooming, Post-Deploy) waived |
| `STANDARD`  | A normal feature path; heavier process phases run conditionally                                |
| `GOVERNED`  | **Default.** The full lifecycle for cross-cutting / production-shipping change                 |
| `REGULATED` | Every phase, no waivers — control-surface change (guardrails, autonomy, PII/financial core)    |

Two rules make this safe, not reckless:

1. **Control phases are never waived.** Right-sizing trims **process** phases only. Testing (8),
   Security & DevSecOps (9), AI Safety (10, when it fires), Code Review (7), the PII classification
   in Discovery (2), the CAB gate in Production (13), and the _no-code-without-a-spec_ invariant in
   Specification (4) run in **every** tier (`phase-gates.yaml › phases[*].applicability.control_phase`).
2. **A safety valve self-corrects under-sizing.** If a run exceeds its declared tier mid-flight
   (scope-ceiling exceeded, coverage drop, a new dependency, an unanticipated control trigger, a
   > 5-step task expansion, or a guardrail touch), `/deliver` **promotes to the next tier**,
   > **re-enters** the skipped phases, and emits a `TIER_ESCALATION` line in the FINAL-REPORT.

The authoritative tier → phase mapping and escalation triggers live in
`docs/process/gates/phase-gates.yaml` (`tiers:`, each phase's `applicability:` block, and
`escalation_triggers:`); the governance projection is in `docs/governance/applicability-matrix.yml`.

---

## Phase 0 — Intake & Prioritization

| Step | Actor    | Action                                                                                                         | Output                      |
| ---- | -------- | -------------------------------------------------------------------------------------------------------------- | --------------------------- |
| 1    | ◈ Human  | Capture problem statement and value/user hypothesis                                                            | Backlog candidate           |
| 2    | ⚡ Agent | Draft a one-line risk class (small fix / normal / high / AI / security / infra) and surface related specs/ADRs | Risk-class suggestion       |
| 3    | ◈ Human  | Assign risk class, owner, and priority; decide go / no-go                                                      | Prioritized item with owner |

Phase 0 happens **before** an Issue exists. It sets the risk class that determines how
many downstream gates apply. No code, no deploy.

---

## Phase 1 — Product / Feature Conception

| Step | Actor    | Action                                                                 | Output                            |
| ---- | -------- | ---------------------------------------------------------------------- | --------------------------------- |
| 1    | ◈ Human  | Write Problem Statement in GitHub Discussion (RFC template)            | Discussion post                   |
| 2    | ⚡ Agent | Read Problem Statement; generate `docs/product/FEAT-{id}/discovery.md` | Discovery Primer                  |
| 3    | ◈ Human  | Viability Review — Product Lead + Tech Lead                            | Issue labeled `status: discovery` |

**Gate:** Issue exists, Discovery doc linked, size label applied, at least one Tech Lead comment.

---

## Phase 2 — Discovery & Requirements Refinement

| Step | Actor    | Action                                                      | Output                             |
| ---- | -------- | ----------------------------------------------------------- | ---------------------------------- |
| 1    | ◈ Human  | User Journey Workshop (async or sync)                       | Journey map, success metrics, NFRs |
| 2    | ⚡ Agent | Extract NFR candidates into `docs/product/FEAT-{id}/nfr.md` | NFR doc (draft)                    |
| 3    | ⚡ Agent | Generate dependency impact analysis from `services.yaml`    | Dependency graph                   |
| 4    | ◈ Human  | NFR Sign-off — Security Lead (required) + Tech Lead         | `nfr.md` approved                  |

**Gate:** NFR doc exists with PII classification, threat surface note, and Security Lead approval.

---

## Phase 3 — Grooming & Backlog Preparation

| Step | Actor    | Action                                                                | Output                 |
| ---- | -------- | --------------------------------------------------------------------- | ---------------------- |
| 1    | ◈ Human  | Story Mapping — break feature into GitHub Issues with labels          | Issues with labels     |
| 2    | ⚡ Agent | Draft acceptance criteria in Gherkin for Issues labeled `needs-ac`    | AC in Issue body       |
| 3    | ⚡ Agent | Pre-populate `specs/features/FEAT-{id}/feature-spec.md` from template | Spec shell             |
| 4    | ◈ Human  | Grooming Ceremony — review AC and spec; Definition of Ready checked   | Sprint board populated |

**Gate:** Definition of Ready (see `docs/process/DEFINITION_OF_READY.md`) — all checklist criteria met.

---

## Phase 4 — Specification & Acceptance Criteria

| Step | Actor    | Action                                                                                  | Output               |
| ---- | -------- | --------------------------------------------------------------------------------------- | -------------------- |
| 1    | ⚡ Agent | Write full `specs/features/FEAT-{id}/feature-spec.md` (SDD cycle, CLAUDE.md §2)         | Spec PR              |
| 2    | ◈ Human  | Spec Review PR — Tech Lead + Security Lead                                              | Approved spec merged |
| 3    | ⚡ CI    | `harness/governance.yml` spec lint gate — spec exists, ADRs valid, agent config present | Gate green           |

**Gate:** Spec PR approved, CI governance job green.

---

## Phase 5 — Architecture & Technical Design

| Step | Actor    | Action                                                            | Output              |
| ---- | -------- | ----------------------------------------------------------------- | ------------------- |
| 1    | ⚡ Agent | Detect if ADR is warranted; draft `docs/adr/ADR-{next}-{slug}.md` | ADR PR              |
| 2    | ◈ Human  | ADR Review — Tech Lead; status Draft → Accepted                   | Accepted ADR merged |
| 3    | ⚡ Agent | Impact propagation — identify files, skills, runbooks to update   | Impact list         |

**Gate:** No architecture-affecting PR without an ADR reference.

---

## Phase 6 — Development

| Step | Actor    | Action                                                                                                   | Output                    |
| ---- | -------- | -------------------------------------------------------------------------------------------------------- | ------------------------- |
| 1    | ⚡ Agent | Session Bootstrap — read `CLAUDE_SESSION_INIT.md`, load skills, read spec                                | `[CONTEXT_GRAPH]` emitted |
| 2    | ⚡ Agent | Planner → Generator → Evaluator harness cycle                                                            | Feature branch            |
| 3    | ◈ Human  | Checkpoint reviews at spec section boundaries                                                            | Continue / redirect       |
| 4    | ⚡ Agent | Update skill files & quickstart docs (CHANGELOG is release-please-generated from the PR title, RFC-0012) | Documentation             |

**Escalation:** `[HITL-ESCALATE]` emitted on guardrail or ADR boundary — see CLAUDE.md §14.

**Gate:** Unit tests green, lint green, pre-commit green, spec reference in new files.

---

## Phase 7 — Code Review & Pull Request

| Step | Actor    | Action                                                                       | Output                |
| ---- | -------- | ---------------------------------------------------------------------------- | --------------------- |
| 1    | ⚡ Agent | Generate PR description from spec                                            | PR opened             |
| 2    | ⚡ CI    | `ci-ai-review.yml` — AI-assisted review posted as PR comment (informational) | Review comment        |
| 3    | ◈ Human  | Code review — ≥1 human approval required                                     | PR approved           |
| 4    | ◈ CI     | `governance-gate.yml` — labels required for autonomy-affecting changes       | Gate green or blocked |

**Gate:** ≥1 human approval, all blocking CI checks green.

---

## Phase 8 — Automated Testing

| Layer          | Command                                                 | Trigger                                                |
| -------------- | ------------------------------------------------------- | ------------------------------------------------------ |
| Unit           | `make test-unit-python` + `-java` + `-go` + `-frontend` | Every PR                                               |
| Integration    | `make test-python`                                      | Every PR to `develop`                                  |
| Security       | `make test-security-python`                             | Every PR                                               |
| Abuse cases    | `pytest tests/abuse_cases/ -m abuse_case`               | PRs touching `src/agents/`                             |
| Model contract | `pytest tests/model_contract/ -m model_contract`        | PRs changing `dependency-manifest.yaml` or `specs/ai/` |
| Chaos          | `pytest tests/chaos/`                                   | Pre-release only                                       |

**Gate:** ≥80% unit coverage, security tests green, abuse case tests green (all blocking).

---

## Phase 9 — Security & DevSecOps

Every PR runs: Bandit · detect-secrets · Trivy · OWASP dep-check · gosec · SpotBugs · ESLint security plugin · CodePreFlight · spec contract validation.

SBOM generated and cosign-attested after every build. DAST (OWASP ZAP) required before production promotion.

**Gate:** Zero HIGH/CRITICAL SAST unmitigated · zero secrets · SBOM attested · governance gate green.

---

## Phase 10 — AI Safety & Agent Governance

> **Conditional gate — required for AI, LLM, or agentic features** (changes under `src/agents/` or `src/guardrails/`). Skipped for non-AI changes (risk-based flow).

| Step | Actor   | Action                                                                                            |
| ---- | ------- | ------------------------------------------------------------------------------------------------- |
| 1    | ⚡ CI   | Prompt-injection + jailbreak abuse-case tests (`tests/abuse_cases/`); OWASP-LLM checks            |
| 2    | ⚡ CI   | Model behavioural contract tests (`tests/model_contract/`); data-leakage / PII non-leakage checks |
| 3    | ◈ Human | Tool-permission review (`infrastructure/agent-tools/tools.yaml`) + autonomy-level sign-off        |
| 4    | ◈ Human | Complete the AI Safety & Agent Governance checklist (`docs/ai-governance/ai-safety-checklist.md`) |

**Gate:** Injection + leakage tests pass · tool permissions reviewed · evals + audit trail present · AI Safety checklist complete. AI Governance Lead approval (ADR-0015, ADR-0053).

---

## Phase 11 — Observability & Operational Readiness

| Step | Actor    | Action                                                                                       |
| ---- | -------- | -------------------------------------------------------------------------------------------- |
| 1    | ⚡ Agent | Verify OTel spans, Prometheus metrics, Grafana panels for new paths                          |
| 2    | ◈ Human  | PRR sign-off (`skills/sre/prr.md`) — health probes, runbook, SLO impact, business value gate |
| 3    | ◈ Human  | Create `docs/sre/runbooks/RB-{next}-{slug}.md` if new failure mode                           |
| 4    | ⚡ CI    | `ci-k8s-probe-lint.yml` — validate all Deployments have startup/liveness/readiness probes    |

**Gate:** PRR ≥90% complete · probe lint green · ≥1 Grafana panel covers new critical path.

---

## Phase 12 — Release Candidate

| Step | Actor   | Action                                                                                                                                                                                                                                                      |
| ---- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | ⚡ Bot  | **release-please** maintains the release PR: bumps `pyproject.toml` + generates `CHANGELOG.md` from Conventional-Commit titles (RFC-0012); `release.yml` syncs `version.txt` + README badge (RFC-0005/0008). No manual `[Unreleased]` move or version bump. |
| 2    | ⚡ CI   | Full suite runs on the release PR: chaos + model-contract tests; SBOM; `make agentic-maturity-check`                                                                                                                                                        |
| 3    | ◈ Human | RC sign-off — Release Manager + Security Lead review/approve the release PR; apply `rc-approved`                                                                                                                                                            |
| 4    | ◈ Human | Merge the release PR → `release.yml` cuts the tag + GitHub Release                                                                                                                                                                                          |

**Gate:** All CI green including chaos. SBOM attested. Zero open P0/P1 issues.

---

## Phase 13 — Production Deployment

5% canary → readiness gate → 25% → readiness gate → 100% → GitHub Release tag.

Rollback: `make rollback` — must complete within MTTR target (`dora_mttr_target_seconds: 3600`).

**Gate:** Each canary step passes SLO burn rate check. Error budget consumed <5% per deploy.

---

## Phase 14 — Post-Deployment & Learn

| Step | Actor    | Action                                                                             |
| ---- | -------- | ---------------------------------------------------------------------------------- |
| 1    | ⚡ CI    | Smoke tests after 100% rollout (`infrastructure/scripts/deploy/smoke-test.sh`)     |
| 2    | ◈ Human  | 24h health check — SRE reviews dashboards at T+1h, T+8h, T+24h                     |
| 3    | ⚡ Agent | Learn stage — `FeedbackLearner` weekly bias summary → Grafana Agent dashboard      |
| 4    | ◈ Human  | Retrospective — DORA delta, security review, agent behaviour review                |
| 5    | ◈ Human  | Backlog grooming — new Issues for bugs or improvements → cycle restarts at Phase 0 |

**Gate:** DORA metrics within SLO targets · no P0 incidents in first 48h · retrospective document created.

---

## Quality Gates Summary

| Phase            | Gate                                                                 | Blocking?              |
| ---------------- | -------------------------------------------------------------------- | ---------------------- |
| 0 Intake         | Risk class + owner assigned; problem/value stated                    | No                     |
| 1 Conception     | Discovery doc linked, size label, Tech Lead comment                  | No                     |
| 2 Discovery      | NFR doc with PII classification, Security Lead approved              | Yes (for DoR)          |
| 3 Grooming       | DoR checklist                                                        | Yes (sprint entry)     |
| 4 Specification  | Spec PR: governance CI + Tech/Security Lead approval                 | Yes                    |
| 5 Architecture   | ADR for any architectural decision                                   | Yes                    |
| 6 Development    | Unit tests green, lint green, pre-commit green                       | Yes                    |
| 7 Code Review    | ≥1 human approval, AI review posted, governance labels if applicable | Yes                    |
| 8 Testing        | ≥80% coverage, security + abuse case tests green                     | Yes                    |
| 9 DevSecOps      | Zero HIGH/CRITICAL SAST, zero secrets, SBOM attested                 | Yes                    |
| 10 AI Safety     | Injection/leakage tests, tool-permission review, AI safety checklist | Yes (AI/agent changes) |
| 11 Observability | PRR ≥90%, probe lint green                                           | Yes (for release)      |
| 12 RC Prep       | Chaos + model contract tests green, RC label                         | Yes                    |
| 13 Deployment    | Canary readiness gate at each step, error budget check               | Yes                    |
| 14 Post-Deploy   | No P0 T+48h, DORA within SLO, retrospective created                  | Yes (sprint close)     |

---

## Related Documents

| Document                   | Path                                          |
| -------------------------- | --------------------------------------------- |
| Definition of Ready        | `docs/process/DEFINITION_OF_READY.md`         |
| Definition of Done         | `docs/process/DEFINITION_OF_DONE.md`          |
| Definition of Release      | `docs/process/DEFINITION_OF_RELEASE.md`       |
| RACI Matrix                | `docs/process/RACI.md`                        |
| HITL Governance (pre-code) | `docs/process/HITL-GOVERNANCE.md`             |
| Sprint Tracking            | `docs/process/SPRINT-TRACKING.md`             |
| Retrospective Guide        | `docs/process/RETROSPECTIVE-GUIDE.md`         |
| Feature Spec Template      | `.github/FEATURE_SPEC_TEMPLATE.md`            |
| RFC Discussion Template    | `.github/DISCUSSION_TEMPLATE/rfc.md`          |
| AI Behavioral Contract     | `CLAUDE.md`                                   |
| SDD Cycle                  | `CLAUDE.md §2`                                |
| Escalation Protocol        | `CLAUDE.md §14`                               |
| PRR Skill                  | `skills/sre/prr.md`                           |
| Deploy-Rollback Skill      | `skills/change-management/deploy-rollback.md` |
