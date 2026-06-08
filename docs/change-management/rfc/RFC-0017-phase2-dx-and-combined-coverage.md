# RFC-0017 — Phase 2: DX baseline + combined coverage visibility

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead, Tech Lead
> **Related RFC:** RFC-0013 (branch protection / flaky-infra exclusion), RFC-0015 (Phase 1)
> **Related ADR:** ADR-0022 (testing strategy)
> **Change type:** Normal

---

## 1. Context

Phase 2 of the uplift roadmap. Two items from the assessment:

- **#5 — coverage gate is unit-only.** `ci.yml` enforces 80% on `tests/unit/` only; code exercised
  solely by integration tests is invisible in the coverage number.
- **#7/#8 — DX hygiene.** A stray untracked `DELIVER.md` sat at repo root; there was no
  `.editorconfig`, so non-Python files had no cross-editor formatting baseline.

## 2. Decision

1. **Combined coverage — reported, not gated.** Integration tests now run with `--cov=src`; a new
   non-blocking **`Combined Coverage (report)`** job downloads the unit + integration coverage
   data, `coverage combine`s them, prints the combined number to the job summary, and uploads it to
   Codecov (`flags: combined`). `[tool.coverage.run] relative_files = true` makes the data
   combinable across jobs.
   **The deterministic 80% gate stays on the unit job.** This is deliberate: integration depends on
   service containers (Kafka/Redis) that flake on Docker Hub, which RFC-0013 explicitly kept out of
   _required_ checks. Gating merges on combined coverage would re-couple merges to flaky infra; so
   combined coverage gives **visibility** (the true number, integration-only gaps surfaced) without
   becoming a merge blocker. If integration doesn't succeed, the report job simply skips.
2. **`.editorconfig`** mirroring the pre-commit hooks (LF, UTF-8, final newline, trim trailing
   whitespace; 4-space Python, tab Makefile/Go, 2-space web/config; Markdown line breaks preserved).
3. **Root cleanup:** remove the stray untracked `DELIVER.md`.

## 3. Alternatives Considered

| Option                                                       | Pros                                             | Cons                                                             | Why rejected                       |
| ------------------------------------------------------------ | ------------------------------------------------ | ---------------------------------------------------------------- | ---------------------------------- |
| A (proposed) — combined coverage _reported_, unit gate stays | True coverage visible; merges stay deterministic | Combined number isn't enforced                                   | —                                  |
| Gate merges on combined (unit+integration) coverage          | Strongest coverage enforcement                   | Couples merges to flaky Kafka/Redis infra (contradicts RFC-0013) | Flakiness would block valid merges |
| Leave unit-only, no combine                                  | No work                                          | Integration-only code stays invisible                            | The gap (#5)                       |

## 4. Impact

| Area                | Impact                                                                           |
| ------------------- | -------------------------------------------------------------------------------- |
| Coverage visibility | Positive — Codecov shows unit+integration union; integration-only paths surfaced |
| Merge gating        | Unchanged — still the deterministic unit 80% gate; new job is non-required       |
| CI cost             | +1 short job + 2 small artifacts (1-day retention)                               |
| DX                  | `.editorconfig` baseline; cleaner repo root                                      |
| New actions         | `download-artifact` SHA-pinned (passes the RFC-0015 pin gate)                    |

## 5. Rollout / Rollback

Merge → next CI run emits a combined-coverage summary + Codecov "combined" flag. Rollback = revert
(CI/config only).

## 6. Out of scope (remaining Phase 2 / later)

- Dependabot patch/minor **auto-merge** (extend `auto-merge.yml`) — deferred (delicate; opt-in).
- Coverage **ratchet** (raise `fail_under` over time) — manual for now.
- Phase 3: org migration → enforced CODEOWNERS reviews / dual-approval.

---

_Approved by:_ _(signatures go here after CAB review)_
