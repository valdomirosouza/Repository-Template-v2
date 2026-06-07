# RFC-0004 — Enforce control-binding declarations as a CI governance gate

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Security Lead, Tech Lead
> **Related Issue:** #83
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Related ADR:** ADR-0060 (Task Atomicity & 2-Skill Budget), ADR-0061 (this gate's decision record)
> **Change type:** Normal

---

## 1. Context

ADR-0060 made the cross-cutting control bindings (privacy / security / compliance) part of
the contract, and `docs/governance/control-applicability-matrix.md` lists the trigger table.
Today, whether a change honours an obligation depends on the agent **remembering** to bind
the matching control. There is no enforcement — a PR can touch `pii_filter.py` and never
declare `privacy/pii`.

This RFC proposes closing that loop in CI: a PR that touches a controlled surface but fails
to declare the matching control is **blocked**.

## 2. Proposed Change

Add a deterministic, offline checker (`scripts/governance/check_control_bindings.py`) and
wire it into the existing **`Governance Checks`** job in `.github/workflows/ci.yml`. The gate:

1. Detects which **control triggers** a PR fires from its changed files (+ optional diff-content regexes), per a canonical ruleset `.github/control-triggers.yml`.
2. Verifies the PR **declared** the matching control (skill or ADR) in its `## Skills — load before executing` block (parsed from the PR body).
3. **Fails** the PR when a fired trigger has no matching declaration.
4. Enforces the **2-skill budget** (max 2 _skill_ controls declared; ambient ADR controls do not count).
5. Flags the **atomicity smell**: ≥ 3 distinct control domains fired ⇒ not atomic, should be split (severity `fail`; `warn` with an `atomic-exception` label, logged).
6. Respects **conditionality** via `docs/governance/applicability-matrix.yml`: a conditional control out of scope (e.g. SOX for a non-US-listed org) emits an `EXEMPT` line, not a failure.
7. Supports an inline allow-marker (`# control-binding: ignore <trigger-id> reason=...`) that suppresses one trigger on one hunk, logged; no blanket ignore.

### Corrections vs the source prompt (`ci-control-binding-gate-prompt-v1.0.0.md`)

The source prompt was written against an earlier repo state. This RFC corrects:

- **ADR number** `ADR-0031` → **ADR-0061** (0031 already exists; highest is 0060).
- **Declared skills** `cicd-pipeline`/`documentation-standards` (do not exist) → the
  implementation task declares `devsecops/pipeline-security` + `engineering/testing-strategy`.
- **`llm-io` trigger** required `devsecops/owasp-llm-top10` (no such skill) → mapped to the
  existing `devsecops/owasp-top10` (which covers the OWASP LLM Top 10); a dedicated skill may
  be added later as its own atomic task.
- **Applicability config**: `docs/governance/applicability-matrix.yml` is the
  **machine-readable companion** to the existing human `control-applicability-matrix.md`
  (cross-linked), not a duplicate.
- This change edits `ci.yml`, so it is filed as an **RFC** (the source prompt omitted one).

## 3. Alternatives Considered

| Option                                | Pros                                                    | Cons                                                                          | Why rejected        |
| ------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------- |
| A (proposed) — CI declaration gate    | Enforces ADR-0060 automatically; deterministic; offline | New checker to maintain; possible false positives (mitigated by allow-marker) | —                   |
| B — keep relying on agent memory      | No new code                                             | Unenforced; the gap ADR-0060 left open                                        | Defeats the point   |
| C — full semantic compliance analysis | Catches real non-compliance                             | Huge scope; non-deterministic; out of reach                                   | Explicit non-goal   |
| D — pre-commit hook only              | Local feedback                                          | Bypassable (`--no-verify`); not authoritative                                 | CI must be the gate |

## 4. Impact Assessment

| Area            | Impact         | Notes                                                                                              |
| --------------- | -------------- | -------------------------------------------------------------------------------------------------- |
| API contracts   | None           | CI-only                                                                                            |
| Database schema | None           | —                                                                                                  |
| PII / Privacy   | Positive       | PII-touching PRs must declare `privacy/pii` + jurisdiction                                         |
| Security        | Positive       | Endpoint/LLM/dependency PRs must declare their security control                                    |
| Performance     | None           | Checker is a few hundred ms in the governance job                                                  |
| Observability   | None           | Suppressions/exceptions logged to job output                                                       |
| Feature flags   | None           | —                                                                                                  |
| Developer flow  | Minor friction | A PR must declare its controls; over-budget/atomicity smells force a split (intended per ADR-0060) |

**Non-goals.** (a) Judging whether code is _truly_ compliant — this enforces declaration
discipline only. (b) Replacing SAST/SCA/secret scanners — the gate sits alongside them and
references them via the `sbom-sca-gate` ambient control.

## 5. Rollout Plan

1. Land ADR-0061 (decision) and this RFC (both require human review).
2. Land the implementation PR (checker + config + tests + CI wiring) — also human-reviewed (touches `ci.yml`).
3. Initially the new step may run in **report mode** for one PR cycle to observe false positives, then flip to **blocking**. (Default config: blocking; document the toggle.)
4. Smoke test: a PR touching `src/guardrails/pii_filter.py` without declaring `privacy/pii` must fail; declaring it must pass; a SOX-triggering PR with SOX out of scope must pass with an exemption note.

## 6. Rollback Plan

Revert the implementation PR (removes the CI step and checker). No data or irreversible
state. The trigger config and applicability matrix are inert without the CI step.

## 7. Timeline

| Milestone                    | Target date                 |
| ---------------------------- | --------------------------- |
| RFC + ADR approved           | 2026-06-07                  |
| Implementation complete      | 2026-06-07                  |
| Blocking enforcement enabled | after one observation cycle |

## 8. Open Questions

- [ ] Should the gate parse declarations from the PR body, the head commit trailer, or both? (MVP: PR body `## Skills` block.)
- [ ] Should a dedicated `devsecops/owasp-llm-top10` skill be created (separate atomic task) so `llm-io` binds a distinct control?

---

_Approved by:_ _(signatures go here after CAB review)_
