# RFC-0014 — Ruleset migration + bypass actor for the release flow

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead, Release Manager, Tech Lead
> **Related Issue:** #116
> **Related RFC:** RFC-0013 (branch protection), RFC-0012 (CHANGELOG ownership), RFC-0006 (manifest mode)
> **Related ADR:** ADR-0027 (ISO 27001 change mgmt), ADR-0057 (version SoT)
> **Change type:** Normal

---

## 1. Context

RFC-0013 applied **legacy branch protection** to `main` requiring nine status checks. That broke
the **release-please** flow: the release PR is authored by `github-actions[bot]` using
`GITHUB_TOKEN`, and **GitHub does not trigger workflows on `GITHUB_TOKEN`-authored PRs** (a
deliberate recursion guard). The nine required checks therefore **never report** on the release
PR, so it is permanently `BLOCKED`.

Release 2.12.1 (PR #115) confirmed this — _"no checks reported on the release-please branch"_ — and
was merged only via `gh pr merge --admin` (possible because RFC-0013 set `enforce_admins: false`).
Without a fix, **every release needs a manual admin override**.

Legacy branch protection has **no per-actor check bypass** (only the all-or-nothing
`enforce_admins`). The bypass-actor capability lives in **repository rulesets**. So the fix is to
migrate `main` protection from legacy branch-protection to an equivalent ruleset that adds a
bypass actor for the release flow.

## 2. Decision

Replace the legacy `main` branch protection with a repository **ruleset** (`main-protection`)
that preserves RFC-0013's guarantees and adds a bypass actor:

- **Same rules:** require a PR (0 approvals) with conversation-thread resolution; require the same
  **9 status checks** (non-strict); block **force-push** (`non_fast_forward`) and **deletion**.
- **Bypass actor:** **Repository admin** role, `bypass_mode: always`. An admin (the owner) can
  merge the release PR via a normal merge — no `--admin` flag, works in the UI — while **every
  non-admin contributor PR remains fully gated** by the 9 checks.
- **Then delete the legacy branch protection** so the ruleset is the single governing mechanism
  (legacy + ruleset both applying would re-block normal admin merges).

This keeps the security posture equivalent to RFC-0013 (admins could already bypass via
`enforce_admins: false`) while removing the per-release `--admin` friction.

## 3. Alternatives Considered

| Option                                           | Pros                                                                                             | Cons                                                                | Why rejected                                                                |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| A (proposed) — ruleset + Repository-admin bypass | Release merges normally; non-admin PRs fully gated; no new secrets                               | Release PR still needs a human admin click (not fully unattended)   | —                                                                           |
| B — PAT/GitHub-App token for release-please      | Checks actually run on the release PR → it merges with no bypass at all; enables true auto-merge | Requires creating + rotating a stored secret (PAT) or a GitHub App  | More setup/secret-management; revisit if hands-off releases are wanted (§8) |
| C — keep `--admin` per release                   | Zero change                                                                                      | Manual override every release; easy to forget; not self-documenting | The problem (#116)                                                          |
| D — drop required checks on `main`               | Release unblocks                                                                                 | Throws away RFC-0013 enforcement entirely                           | Under-protects                                                              |

## 4. Implementation

`POST /repos/:owner/:repo/rulesets` (target = default branch, enforcement = active):

```jsonc
{
  "name": "main-protection",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }, // Repository admin
  ],
  "conditions": {
    "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] },
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
      },
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          { "context": "Governance Checks" },
          { "context": "Lint" },
          { "context": "Unit Tests" },
          { "context": "Contract Drift Check" },
          { "context": "Conventional PR title" },
          { "context": "Spec reference" },
          { "context": "Version consistency" },
          { "context": "GitHub Issue referenced" },
          { "context": "Detect Secrets" },
        ],
      },
    },
  ],
}
```

Then `DELETE /repos/:owner/:repo/branches/main/protection`.

**Verification:** `GET /repos/:owner/:repo/rules/branches/main` as an admin returns **no rules**
(bypass effective for admins); as a non-admin it would return all four rules. The next release PR
merges without `--admin`.

## 5. Impact Assessment

| Area                            | Impact                             | Notes                                                      |
| ------------------------------- | ---------------------------------- | ---------------------------------------------------------- |
| Release flow                    | Positive                           | Release PR merges via normal admin merge — no `--admin`    |
| Non-admin PRs                   | Unchanged                          | Still gated by all 9 checks + PR + conversation resolution |
| Force-push / deletion of `main` | Still blocked                      | Preserved                                                  |
| Security posture                | Equivalent to RFC-0013             | Admins could already bypass (`enforce_admins: false`)      |
| Mechanism                       | legacy branch protection → ruleset | Single governing mechanism after legacy is deleted         |

## 6. Rollout Plan

1. Land this RFC.
2. Create the `main-protection` ruleset (above); verify via `GET .../rules/branches/main`.
3. Delete the legacy branch protection; confirm `GET .../branches/main/protection` → 404.
4. Validate at the next release: the release PR merges without `--admin`.

## 7. Rollback Plan

Delete the ruleset (`DELETE /repos/:owner/:repo/rulesets/:id`) and re-`PUT` the RFC-0013 legacy
protection. No data/state impact.

## 8. Open Questions

- [ ] Adopt **Option B (PAT/App token)** later for fully unattended releases (checks run on the
      release PR, auto-merge possible)?
- [ ] Confirm the Repository-admin `actor_id` (5) resolves correctly on this personal repo at apply time.

---

_Approved by:_ _(signatures go here after CAB review)_
