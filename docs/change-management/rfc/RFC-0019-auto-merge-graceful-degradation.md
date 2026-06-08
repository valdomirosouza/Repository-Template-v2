# RFC-0019 — Auto-merge: enable the setting + degrade gracefully

> **Status:** Accepted (applied 2026-06-07)
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead
> **Related RFC:** RFC-0003 (auto-merge scope), REM-005 · **Change type:** Normal

---

## 1. Context

The scoped docs/deps **auto-merge** workflow (`.github/workflows/auto-merge.yml`, REM-005) failed
on every eligible PR with `GraphQL: Auto merge is not allowed for this repository
(enablePullRequestAutoMerge)`. Cause: the repo-level **"Allow auto-merge" setting was off** —
which is GitHub's **default**, so this also breaks for **every template clone** until a maintainer
flips it. The failing (non-required) check produced a recurring red ✗ on docs PRs.

## 2. Decision

1. **Enable** `allow_auto_merge` on this repo (`PATCH /repos/{owner}/{repo} -F allow_auto_merge=true`)
   so the documented docs/deps auto-merge actually works.
2. **Harden** the "Enable auto-merge" step: if `gh pr merge --auto` fails specifically because
   auto-merge is disabled, emit a `::warning::` explaining how to enable it and **exit 0** (don't
   fail the check). Other errors still fail. This makes the template robust for clones that haven't
   enabled the setting yet — they get a helpful hint instead of a red ✗.

Scope/safety of auto-merge are unchanged (REM-005): only docs-only PRs (excluding
`CLAUDE.md`/`AGENTS.md`/`docs/adr/`) and Dependabot, after required checks pass.

## 3. Alternatives Considered

| Option                      | Why not                                                                 |
| --------------------------- | ----------------------------------------------------------------------- |
| Enable the setting only     | Fixes this repo, but template clones still flake (setting defaults off) |
| Harden only (don't enable)  | Removes the noise but leaves the feature dead here                      |
| Disable/delete the workflow | Throws away the intended, scoped low-risk auto-merge                    |

## 4. Impact

- Docs-only / Dependabot PRs now **auto-merge** here after the required checks pass (human review
  still required for everything else). The release PR (#118) is bot-authored + non-docs → **not**
  auto-merged (stays manual).
- Template clones: graceful warning instead of a failing check until they enable the setting.

## 5. Rollback

`PATCH … -F allow_auto_merge=false` and/or revert the workflow change.

---

_Approved by:_ _(signatures go here after CAB review)_
