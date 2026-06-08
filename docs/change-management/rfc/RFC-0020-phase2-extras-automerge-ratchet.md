# RFC-0020 — Phase 2 extras: Dependabot patch/minor auto-merge + coverage ratchet

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead, Tech Lead
> **Related RFC:** RFC-0015 (Dependabot grouping), RFC-0017 (coverage), RFC-0019 (auto-merge), REM-005
> **Related ADR:** ADR-0022 (testing strategy) · **Change type:** Normal

---

## 1. Context

Two deferred Phase-2 items from the uplift roadmap:

1. **Dependabot auto-merge is too broad.** After RFC-0019 enabled auto-merge, the workflow
   auto-merges **all** Dependabot PRs once checks pass — including **major** version bumps, which
   carry real breaking-change risk and deserve human review.
2. **Coverage floor is static at 80%** while actual unit coverage is **86.6%** — leaving ~6.6% of
   silent erosion headroom before the gate would notice.

## 2. Decision

1. **Scope Dependabot auto-merge to patch/minor.** Add `dependabot/fetch-metadata` to
   `auto-merge.yml` and mark a Dependabot PR eligible **only** when `update-type` is
   `semver-patch` or `semver-minor`. **Major** bumps (and unknown) fall back to manual review.
   Non-Dependabot scope is unchanged (docs-only, excluding CLAUDE/AGENTS/ADR — REM-005).
2. **Ratchet the coverage floor 80% → 85%** (`pyproject.toml` `fail_under` + the unit job's
   `--cov-fail-under`). 85 sits ~1.5% below current (86.6%) — a small buffer for normal churn while
   locking in today's quality. Policy: raise as coverage rises, never lower. The integration run
   stays `--cov-fail-under=0` (data only) and the combined report stays informational (RFC-0017).

## 3. Alternatives Considered

| Item       | Alternative                                  | Why not                                                            |
| ---------- | -------------------------------------------- | ------------------------------------------------------------------ |
| Auto-merge | Keep auto-merging all Dependabot incl. major | Major bumps break things; should be reviewed                       |
| Auto-merge | Auto-merge patch only (not minor)            | Minor bumps are low-risk under semver + full CI; over-conservative |
| Ratchet    | Set `fail_under` = 86 (no buffer)            | Normal churn could cause false failures                            |
| Ratchet    | Auto-bumping baseline via a bot commit       | More machinery; revisit later                                      |
| Ratchet    | Per-module floors                            | Needs a plugin/custom script; out of scope                         |

## 4. Impact

| Area           | Impact                                                                |
| -------------- | --------------------------------------------------------------------- |
| Dependency PRs | patch/minor auto-merge after checks; **major** → manual review        |
| Coverage gate  | 80% → **85%** (verified: current 86.6% passes with headroom)          |
| New action     | `dependabot/fetch-metadata` SHA-pinned (passes the RFC-0015 pin gate) |
| Risk           | Lower — breaking deps gated; coverage can't silently erode below 85%  |

## 5. Rollout / Rollback

Merge → next Dependabot PR is auto-merged only if patch/minor; the unit gate enforces 85%.
Rollback = revert (restores broad auto-merge + 80% floor).

---

_Approved by:_ _(signatures go here after CAB review)_
