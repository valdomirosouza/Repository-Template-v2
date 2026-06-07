# RFC-0005 — Keep version.txt in sync on release-please PRs

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Release Manager, Tech Lead
> **Related Issue:** #90
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Related ADR:** ADR-0057 (version.txt single source of truth)
> **Change type:** Normal

---

## 1. Context

`.github/workflows/release.yml` runs `google-github-actions/release-please-action` with
`release-type: python`, which bumps the version in `pyproject.toml` on its release PR
branch (`release-please--branches--main`). However **`version.txt` is the single source of
truth** (ADR-0057), and the `pr-governance` version-consistency gate fails when
`version.txt` ≠ `pyproject.toml`.

release-please does not touch `version.txt`, so its release PRs drift: PR #66
(`chore(main): release 2.11.0`) bumps `pyproject.toml` → 2.11.0 while `version.txt` stays
`2.10.2`. Merging it would land an inconsistent `main`.

`version.txt` is consumed **raw** — `Path("version.txt").read_text().strip()` — by nine
places (Makefile, `src/shared/config.py`, `scripts/generate_context_graph.py`,
`scripts/template-init.sh`, `scripts/check_version_consistency.py`, two CI workflows, two
unit tests). It therefore **cannot carry release-please annotation markers**
(`x-release-please-version`), which rules out release-please's `extra-files` "generic"
updater (the marker would break every raw consumer).

## 2. Proposed Change

Add one step to the `release-please` job in `release.yml`, immediately **after** the action,
that mirrors the bumped `pyproject.toml` version into `version.txt` on the release PR branch:

```yaml
- name: Sync version.txt on the release PR (ADR-0057 SoT, RFC-0005)
  continue-on-error: true
  env: { GH_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
  run: |
    BRANCH=release-please--branches--main
    git fetch origin "$BRANCH" || { echo "No release PR branch"; exit 0; }
    git checkout "$BRANCH"
    VER="$(grep -m1 -E '^version *= *"' pyproject.toml | sed -E 's/^version *= *"([^"]+)".*/\1/')"
    [ -n "$VER" ] || exit 0
    [ "$(cat version.txt)" = "$VER" ] && { echo "consistent"; exit 0; }
    printf '%s\n' "$VER" > version.txt
    git config user.name "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    git commit -am "chore: sync version.txt to $VER (ADR-0057, RFC-0005)"
    git push origin "$BRANCH"
```

**Why this is reliable.** release-please force-pushes its branch each run, but this step runs
**after the action in the same job on every push to `main`**, so it re-applies the
`version.txt` sync every time. Pushing to `release-please--branches--main` does **not**
re-trigger `release.yml` (it triggers on `push` to `main` only), so there is no loop. It is
`continue-on-error: true` so it never blocks the (already best-effort) release job, and a
no-op when the branch is absent or already consistent.

**Effect on PR #66:** the next push to `main` (this RFC merging) runs the step, which adds a
`chore: sync version.txt to 2.11.0` commit to #66's branch — making #66 consistent and
mergeable under the version-consistency gate.

## 3. Alternatives Considered

| Option                                                          | Pros                                                         | Cons                                                                                         | Why rejected                                   |
| --------------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| A (proposed) — post-action sync step                            | Reliable under force-push; no consumer changes; minimal diff | Adds a bot commit to the release PR                                                          | —                                              |
| B — release-please `extra-files` generic updater on version.txt | Declarative, idiomatic                                       | Requires `x-release-please-version` markers in version.txt, which breaks all 9 raw consumers | Not feasible without invasive consumer changes |
| C — make pyproject.toml the SoT                                 | Aligns with release-please default                           | Contradicts ADR-0057; touches every consumer + the gate                                      | Out of scope; bigger decision                  |
| D — manual edit of every release PR                             | No automation change                                         | Error-prone, defeats automation                                                              | Unreliable                                     |

## 4. Impact Assessment

| Area            | Impact   | Notes                                                            |
| --------------- | -------- | ---------------------------------------------------------------- |
| API / DB / PII  | None     | CI/release-tooling only                                          |
| Security        | Neutral  | Uses the default `GITHUB_TOKEN` already scoped `contents: write` |
| Release process | Positive | Release PRs stay ADR-0057-consistent; version gate stays green   |
| Observability   | None     | Step logs the sync to the job output                             |

**Non-goal:** changing which file is the SoT (remains `version.txt`, ADR-0057), or the
release cadence/mechanism.

## 5. Rollout Plan

1. Merge this PR to `main` after DevOps/Release-Manager review (touches `.github/workflows/` → human review by design).
2. On the merge push, `release.yml` runs and the new step syncs `version.txt` onto PR #66 → #66 becomes consistent.
3. Smoke test: confirm PR #66 gains a `chore: sync version.txt to 2.11.0` commit and that `version.txt` == `pyproject.toml` on its branch.

## 6. Rollback Plan

Revert this PR (removes the step). No data or irreversible state; release PRs simply revert
to the prior (drifting) behaviour.

## 7. Timeline

| Milestone               | Target date                     |
| ----------------------- | ------------------------------- |
| RFC approved            | 2026-06-07                      |
| Implementation complete | 2026-06-07                      |
| Verified on PR #66      | next push to `main` after merge |

## 8. Open Questions

- [ ] Long term, should the repo adopt release-please **manifest mode** and reconsider whether `version.txt` or `pyproject.toml` is the canonical bump target? (Larger change; tracked separately if desired.)

---

_Approved by:_ _(signatures go here after CAB review)_
