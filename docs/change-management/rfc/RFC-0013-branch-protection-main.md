# RFC-0013 — Branch protection for `main` (Balanced policy)

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead, Tech Lead, Security Lead
> **Related Issue:** #112
> **Related RFC:** RFC-0001/0002 (branch hygiene), RFC-0003 (auto-merge review gating), RFC-0012 (CHANGELOG ownership)
> **Related ADR:** ADR-0027 (ISO 27001 change mgmt)
> **Change type:** Normal

---

## 1. Context

`main` currently has **no branch protection and no rulesets** (verified:
`GET branches/main/protection` → 404; `GET rulesets` → `[]`). CI is therefore **advisory** —
GitHub does not block merging a PR with failing checks, nor direct pushes to `main`. The
gating that has worked in practice comes from repo _conventions_ (auto-merge only auto-approves
docs-only PRs; RFC-0003 holds contract/ADR PRs; humans wait for green) — not from enforcement.

This RFC makes the high-signal gates **enforced** without breaking the established flows
(docs auto-merge, `develop → main` merge commits, release-please).

## 2. Decision — Balanced policy

Apply the following protection to `main` (via the branch-protection API):

```jsonc
{
  "required_status_checks": {
    "strict": false, // don't force branch-up-to-date (keeps develop→main / release flows smooth)
    "contexts": [
      "Governance Checks",
      "Lint",
      "Unit Tests",
      "Contract Drift Check",
      "Conventional PR title",
      "Spec reference",
      "Version consistency",
      "GitHub Issue referenced",
      "Detect Secrets",
    ],
  },
  "required_pull_request_reviews": { "required_approving_review_count": 0 }, // require a PR, but no human approval — preserves docs auto-merge
  "required_conversation_resolution": true,
  "enforce_admins": false, // owner can still operate release/merge flows
  "allow_force_pushes": false,
  "allow_deletions": false, // main cannot be force-pushed or deleted
  "restrictions": null,
}
```

### Why these choices

- **Required checks are curated + deterministic + always-run.** All nine run on _every_ PR to
  `main` (ci.yml and pr-governance have no path filters; secret-scanning runs on all PRs), and
  their names match the actual check-run names exactly — so no PR can deadlock waiting on a
  check that never reports.
- **Flaky infra checks excluded** (`Integration Tests`, `Build Docker Image`, `DAST`,
  `Generate SBOM`): these depend on Docker Hub and timed out repeatedly this session; making
  them _required_ would block merges on transient infra, not real defects. They still run and
  are visible — just not blocking.
- **0 required approvals** keeps the docs **auto-merge** flow intact (the bot's auto-approval is
  not relied upon for a review count) while still **requiring a PR** (no direct pushes to `main`).
- **`enforce_admins: false`** so the owner can still drive release-please / `develop → main`
  merges without self-lockout.
- **`allow_deletions: false`** hardens against the kind of branch loss seen earlier (RFC-0001).

## 3. Alternatives Considered

| Option                                                | Pros                                                                                | Cons                                                                           | Why rejected                              |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------- |
| A (proposed) — Balanced                               | Enforces high-signal gates; preserves auto-merge + release flows; no flake-blocking | No enforced human review                                                       | —                                         |
| B — Strict (1 review + infra checks + enforce_admins) | Strongest                                                                           | Risks docs auto-merge (bot-approval counting) and flake-blocking on Docker Hub | Higher friction; revisit later if desired |
| C — Minimal (a few checks)                            | Lowest friction                                                                     | Leaves most gates advisory                                                     | Under-enforces                            |
| D — leave unprotected                                 | No work                                                                             | CI stays advisory; direct pushes/force-push/deletion possible                  | The problem (#112)                        |

## 4. Impact Assessment

| Area                              | Impact                               | Notes                                                |
| --------------------------------- | ------------------------------------ | ---------------------------------------------------- |
| Merges to `main`                  | Now blocked unless the 9 checks pass | Real enforcement of existing gates                   |
| Docs auto-merge                   | Preserved                            | 0 required reviews; checks the bot already waits for |
| `develop → main` / release-please | Preserved                            | Non-strict; release PR passes the same checks        |
| Force-push / deletion of `main`   | Blocked                              | Hardening                                            |
| Admins                            | Not enforced                         | Owner retains operational override                   |

**Non-goal:** requiring human review (Strict, option B) or gating on flaky infra checks.

## 5. Rollout Plan

1. Land this RFC (docs).
2. Apply the protection via `PUT repos/:owner/:repo/branches/main/protection` with the JSON above.
3. Smoke test: open a trivial PR → confirm it cannot merge until the 9 checks are green; confirm a docs-only PR still auto-merges; confirm `main` rejects force-push/deletion.

## 6. Rollback Plan

`DELETE repos/:owner/:repo/branches/main/protection` (or relax specific fields). No data/state
impact; reverts to the current advisory posture.

## 7. Timeline

| Milestone          | Target date |
| ------------------ | ----------- |
| RFC approved       | 2026-06-07  |
| Protection applied | 2026-06-07  |
| Smoke-tested       | next PR     |

## 8. Open Questions

- [ ] Promote to **Strict** (1 required review + infra checks) once the Docker-Hub flakiness is
      mitigated (e.g. registry mirror / retries)?
- [ ] Mirror an equivalent (lighter) protection on `develop`?

---

_Approved by:_ _(signatures go here after CAB review)_
