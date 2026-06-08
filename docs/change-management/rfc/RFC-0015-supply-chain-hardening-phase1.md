# RFC-0015 — Supply-chain hardening (Phase 1): SHA-pin all actions + full SCA

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Security Lead
> **Related ADR:** ADR-0029 (DevSecOps pipeline security)
> **Change type:** Normal

---

## 1. Context

A repository uplift assessment found two supply-chain gaps in an otherwise high-maturity repo:

1. **Inconsistent action pinning.** 20 workflow `uses:` were SHA-pinned but 8 workflows still
   used mutable tags (`actions/checkout@v4`, `actions/github-script@v7`,
   `github/codeql-action/*@v3`, `sigstore/cosign-installer@v3`, `astral-sh/setup-uv@v3`,
   `anchore/sbom-action/download-syft@v0`, `actions/upload-artifact@v4`,
   `zaproxy/action-full-scan@v0.10.0`). Mutable tags are the classic CI compromise vector
   (an attacker who moves a tag runs code in CI with the workflow's token scopes).
2. **Partial SCA.** Dependabot covered only `pip` + `github-actions`, leaving the multi-language
   monorepo's **npm** (frontend), **Go** (event-worker), **Maven** (domain-service), and
   **Docker** base images with no automated vulnerability/version updates — despite CLAUDE.md
   A06 mandating SCA at every boundary.

## 2. Decision

**Part A — SHA-pin every action + enforce it.**

- Pin all 8 straggler workflows to full commit SHAs. `checkout` and `upload-artifact` are aligned
  to the repo's existing standard pins (v6.0.2 / v7.0.1); the rest are pinned to the current SHA
  of their in-use major (no behaviour change), with a `# <version>` comment.
- Add `scripts/governance/check_action_pins.sh` and run it in the **Governance Checks** CI job
  (already a required status check) — fails the build if any `uses:` is not a 40-char SHA
  (local `./` and `docker://…@sha256:` refs are exempt). Add a `make check-action-pins` target.
  Dependabot (`github-actions`) keeps the pins current.

**Part B — Full-stack SCA.** Extend `.github/dependabot.yml` with `npm` (`/frontend/frontend`),
`gomod` (`/services/event-worker`), `maven` (`/services/domain-service`), and `docker`
(`/`, `/services/event-worker`, `/frontend/frontend`). Minor/patch updates are grouped per
ecosystem to limit PR noise; majors stay individual for review.

## 3. Alternatives Considered

| Option                                   | Pros                                                        | Cons                                        | Why rejected                                  |
| ---------------------------------------- | ----------------------------------------------------------- | ------------------------------------------- | --------------------------------------------- |
| A (proposed) — pin all + gate + full SCA | Closes both gaps; self-enforcing; Dependabot maintains pins | One-time churn across 8 files               | —                                             |
| Tag-pin but skip the gate                | Less work                                                   | Drift returns silently                      | No enforcement = recurrence                   |
| `zizmor`/`actionlint` for pinning        | Richer CI-security linting                                  | New dependency; broader scope               | Adopt later; a focused grep gate suffices now |
| Renovate instead of Dependabot           | Grouping/auto-merge, more ecosystems                        | Migration off the existing Dependabot setup | Out of Phase 1 scope                          |

## 4. Impact Assessment

| Area            | Impact          | Notes                                                                                                                        |
| --------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| CI supply chain | Positive        | No mutable action tags; consistent SLSA posture; enforced going forward                                                      |
| SCA coverage    | Positive        | Python + Actions + npm + Go + Maven + Docker (was 2 of 6)                                                                    |
| Behaviour       | None            | SHAs pin the same code currently running; no version jumps except checkout/upload-artifact aligned to existing repo standard |
| PR volume       | Slight increase | New Dependabot ecosystems; mitigated by minor/patch grouping                                                                 |
| Required checks | Unchanged       | Pin gate runs inside the existing "Governance Checks" job                                                                    |

## 5. Rollout Plan

1. Merge this PR (pins + gate + Dependabot).
2. Confirm the "Governance Checks" job runs the pin check green.
3. Dependabot opens grouped PRs for the new ecosystems on its next run.

## 6. Rollback Plan

Revert the PR. No data/state impact (CI config only).

## 7. Out of scope (later phases)

- Phase 2: combined unit+integration coverage gate, `.editorconfig`, root cleanup, Dependabot auto-merge.
- Phase 3: org migration → enforce CODEOWNERS reviews / dual-approval (the governance-enforcement lever).
- `RELEASE_PLEASE_TOKEN` provisioning (RFC-0014) — owner action, already wired.

---

_Approved by:_ _(signatures go here after CAB review)_
