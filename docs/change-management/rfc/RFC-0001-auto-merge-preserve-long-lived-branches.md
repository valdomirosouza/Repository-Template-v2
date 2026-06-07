# RFC-0001 — Auto-merge must preserve long-lived integration branches

> **Status:** Approved — implemented in PR #65 (merged to `main` as `03cea96`, 2026-06-07)
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Tech Lead
> **Related Issue:** #64
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Change type:** Normal

---

## 1. Context

This repository uses a **develop-based flow**: work is integrated on the long-lived
`develop` branch and promoted to `main` via PR. The `auto-merge` workflow
(`.github/workflows/auto-merge.yml`, REM-005) auto-approves and squash-merges
documentation-only PRs.

Its final step runs:

```yaml
gh pr merge "$PR_NUMBER" --repo "$REPO" --squash --auto --delete-branch
```

The `--delete-branch` flag deletes the PR **head** branch after merge. For a `develop → main`
PR the head branch is `develop`, so the workflow **deletes the long-lived integration
branch on every eligible merge**. This was observed after PR #62 and PR #63 — `develop` had
to be manually recreated each time.

The repository setting `delete_branch_on_merge` is correctly `false`; the deletion comes
solely from the explicit workflow flag, which overrides the repo setting. The flag was
written assuming head branches are always disposable feature branches, which does not hold
for this repo's branching model.

## 2. Proposed Change

Guard the `--delete-branch` flag on the head ref so long-lived integration branches are
preserved while disposable feature branches are still cleaned up:

```yaml
- name: Enable auto-merge
  if: steps.scope.outputs.eligible == 'true'
  env:
    HEAD_REF: ${{ github.head_ref }}
  run: |
    # Keep long-lived integration branches; clean up disposable feature branches.
    if [[ "$HEAD_REF" == "develop" || "$HEAD_REF" == "main" ]]; then
      gh pr merge "$PR_NUMBER" --repo "$REPO" --squash --auto
    else
      gh pr merge "$PR_NUMBER" --repo "$REPO" --squash --auto --delete-branch
    fi
```

No other workflow behaviour changes: eligibility scoping (docs-only / Dependabot),
auto-approve, and squash semantics are untouched.

## 3. Alternatives Considered

| Option                                             | Pros                                                                    | Cons                                                                                                  | Why rejected                        |
| -------------------------------------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------- |
| A (proposed) — guard `--delete-branch` on head ref | Preserves `develop`/`main`; still cleans feature branches; minimal diff | Branch allow-list is hard-coded in the workflow                                                       | —                                   |
| B — drop `--delete-branch` entirely                | Simplest one-line change                                                | Leaves merged feature branches uncleaned; relies on repo setting (`false`) so nothing is ever cleaned | Loses useful feature-branch hygiene |
| C — rely only on repo `delete_branch_on_merge`     | No workflow edit                                                        | The explicit flag overrides the setting, so it would not fix the bug                                  | Does not solve the problem          |

## 4. Impact Assessment

| Area            | Impact | Notes                                                                     |
| --------------- | ------ | ------------------------------------------------------------------------- |
| API contracts   | None   | CI-only change                                                            |
| Database schema | None   | —                                                                         |
| PII / Privacy   | None   | No data processing                                                        |
| Security        | None   | No new attack surface; no permission change; auto-approve scope unchanged |
| Performance     | None   | —                                                                         |
| Observability   | None   | —                                                                         |
| Feature flags   | None   | —                                                                         |

## 5. Rollout Plan

1. Merge this PR to `main` after DevOps Lead approval (workflow change is not auto-merge eligible — it touches `.github/workflows/`, a non-docs path, so it requires human review by design).
2. No deploy step — GitHub Actions picks up the new workflow definition on the next eligible PR.
3. Smoke test: the next docs-only auto-merge from `develop → main` must leave `origin/develop` intact.
4. Observation window: confirm `develop` survives the following two auto-merged PRs.

## 6. Rollback Plan

Revert this PR. The previous workflow behaviour is restored immediately; no data or
irreversible state is involved. If `develop` is ever deleted again, recreate it with
`git push -u origin develop` from a local checkout at `origin/main`.

## 7. Timeline

| Milestone               | Target date        |
| ----------------------- | ------------------ |
| RFC approved            | 2026-06-07         |
| Implementation complete | 2026-06-07         |
| Staging deploy          | n/a (CI workflow)  |
| Production deploy       | on merge to `main` |

## 8. Open Questions

- [ ] Should the protected-branch list be sourced from a single config (e.g. repo variable) instead of hard-coded, if more long-lived branches are added later?

---

_Approved by:_ _(signatures go here after CAB review)_
