# RFC-0002 — Merge commits (not squash) for long-lived integration branches

> **Status:** Approved — implemented in PR #68 (merged to `main`, 2026-06-07)
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Tech Lead
> **Related Issue:** #64
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Related RFC:** RFC-0001 (auto-merge branch preservation)
> **Change type:** Normal

---

## 1. Context

This repository uses a **develop-based flow**: `develop` is a long-lived integration
branch promoted to `main` via PR. The `auto-merge` workflow squash-merges eligible
(docs-only) PRs.

Squash-merging a long-lived branch into `main` rewrites the merged commits into a single
new commit on `main`. As a result `develop` is **never an ancestor of `main`** — after each
merge the two branches are content-identical but have different commit SHAs, and Git reports
`develop` as "ahead 1, behind 1". Realigning them requires a `git push --force-with-lease`
on the shared `develop` branch after every merge — a destructive operation on a shared
branch, and a recurring source of friction (observed across PRs #62, #63, #67).

RFC-0001 stopped auto-merge from _deleting_ `develop`; this RFC removes the _divergence_
itself by changing how long-lived branches are merged.

## 2. Proposed Change

In `.github/workflows/auto-merge.yml`, select the merge method by head ref:

```yaml
- name: Enable auto-merge
  if: steps.scope.outputs.eligible == 'true'
  env:
    HEAD_REF: ${{ github.head_ref }}
  run: |
    if [[ "$HEAD_REF" == "develop" || "$HEAD_REF" == "main" ]]; then
      # Long-lived integration branch: merge commit preserves ancestry (no divergence), keep branch (RFC-0001, RFC-0002).
      gh pr merge "$PR_NUMBER" --repo "$REPO" --merge --auto
    else
      # Disposable feature branch: squash for clean history, delete after merge (RFC-0001).
      gh pr merge "$PR_NUMBER" --repo "$REPO" --squash --auto --delete-branch
    fi
```

Effect:

- **`develop → main`** uses a **merge commit** → `develop` stays a true ancestor of `main`;
  no divergence, no force-push ever needed.
- **feature branches** keep **squash + delete** → clean linear history, automatic cleanup.

Merge commits are already enabled at the repo level (`allow_merge_commit: true`); no
repository setting change is required.

## 3. Alternatives Considered

| Option                                                                | Pros                                                              | Cons                                                                           | Why rejected                              |
| --------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------- |
| A (proposed) — merge commit for `develop`/`main`, squash for features | Eliminates divergence; no force-push; keeps feature history clean | `main` history shows merge commits                                             | —                                         |
| B — keep squash, force-align `develop` after each merge               | No workflow change                                                | Recurring destructive force-push on a shared branch; manual step               | Fragile and against shared-branch hygiene |
| C — squash everything, treat `develop` as disposable                  | Simplest                                                          | Breaks the develop-based flow; `develop` would be deleted/recreated constantly | Wrong model for this repo                 |

## 4. Impact Assessment

| Area            | Impact  | Notes                                                                              |
| --------------- | ------- | ---------------------------------------------------------------------------------- |
| API contracts   | None    | CI-only change                                                                     |
| Database schema | None    | —                                                                                  |
| PII / Privacy   | None    | —                                                                                  |
| Security        | None    | No new surface; auto-approve scope and eligibility unchanged                       |
| Performance     | None    | —                                                                                  |
| Observability   | None    | —                                                                                  |
| Feature flags   | None    | —                                                                                  |
| Git history     | Changed | `develop → main` promotions appear as merge commits; feature branches still squash |

Note: the `pr-governance` "Conventional PR title" gate validates the **PR title**, which is
unaffected by merge method, so governance gates continue to apply.

## 5. Rollout Plan

1. Merge this PR to `main` after DevOps Lead approval (non-docs path → not auto-merge eligible → human review by design).
2. No deploy step — GitHub Actions uses the updated workflow on the next eligible PR.
3. Smoke test: the next docs-only `develop → main` auto-merge must produce a **merge commit** on `main` and leave `develop` as an ancestor of `main` (`git merge-base --is-ancestor develop main` succeeds; no "ahead/behind").

## 6. Rollback Plan

Revert this PR — restores squash behaviour for long-lived branches (RFC-0001 preservation
still applies). No data or irreversible state involved.

## 7. Timeline

| Milestone               | Target date        |
| ----------------------- | ------------------ |
| RFC approved            | 2026-06-07         |
| Implementation complete | 2026-06-07         |
| Staging deploy          | n/a (CI workflow)  |
| Production deploy       | on merge to `main` |

## 8. Open Questions

- [ ] Should manual (non-auto) `develop → main` merges also standardise on `--merge` via a documented convention or CONTRIBUTING note?

---

_Approved by:_ _(signatures go here after CAB review)_
