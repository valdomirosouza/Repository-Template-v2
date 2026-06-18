# RFC Index

Request-for-Change (RFC) register for Repository-Template-v2. Mirrors `docs/adr/README.md`.
RFCs capture **normal/emergency changes** to CI/CD, release tooling, branch protection, and
supply-chain posture (ISO 27001 change management — ADR-0027). New RFCs use
[`RFC-TEMPLATE.md`](RFC-TEMPLATE.md).

> **Status vocabulary:** Draft · Under Review · Proposed · Approved · Accepted · Implemented ·
> Rejected · Withdrawn · Superseded. Advance the status field **on merge** — a shipped change must
> not sit in `Under Review` (the most common register-hygiene defect; see the 2026-06-16 audit).

| RFC                                                                  | Title                                                                | Status                                                          | Date       |
| -------------------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------- | ---------- |
| [RFC-0001](RFC-0001-auto-merge-preserve-long-lived-branches.md)      | Auto-merge: preserve long-lived branches                             | Implemented                                                     | 2026-06-07 |
| [RFC-0002](RFC-0002-merge-commit-for-long-lived-branches.md)         | Merge-commit for long-lived branches                                 | Implemented                                                     | 2026-06-07 |
| [RFC-0003](RFC-0003-exclude-governance-artifacts-from-auto-merge.md) | Exclude governance/contract artifacts from auto-merge                | Implemented                                                     | 2026-06-07 |
| [RFC-0004](RFC-0004-control-binding-ci-gate.md)                      | Control-binding declarations as a CI gate                            | Implemented                                                     | 2026-06-07 |
| [RFC-0005](RFC-0005-release-please-version-txt-sync.md)              | Keep version.txt in sync on release-please PRs                       | Implemented                                                     | 2026-06-07 |
| [RFC-0006](RFC-0006-release-please-manifest-mode.md)                 | Migrate release-please to manifest mode                              | Implemented                                                     | 2026-06-07 |
| [RFC-0007](RFC-0007-action-deprecation-node24-bumps.md)              | Resolve release-please rename + Node action deprecations             | Implemented                                                     | 2026-06-07 |
| [RFC-0008](RFC-0008-readme-version-badge-sync.md)                    | Sync the README version badge on release PRs                         | Implemented                                                     | 2026-06-07 |
| [RFC-0009](RFC-0009-image-publish-graceful-skip.md)                  | Skip image publish gracefully when no registry configured            | Implemented                                                     | 2026-06-07 |
| [RFC-0010](RFC-0010-ghcr-github-token-publish.md)                    | Publish release images to GHCR via GITHUB_TOKEN                      | Implemented                                                     | 2026-06-07 |
| [RFC-0011](RFC-0011-fix-sbom-image-attestation.md)                   | Remove misplaced SBOM image-attestation                              | Implemented                                                     | 2026-06-07 |
| [RFC-0012](RFC-0012-changelog-single-ownership.md)                   | Single CHANGELOG owner: release-please                               | Implemented                                                     | 2026-06-07 |
| [RFC-0013](RFC-0013-branch-protection-main.md)                       | Branch protection for `main`                                         | Superseded by RFC-0021 (enforced ruleset ratified)              | 2026-06-07 |
| [RFC-0014](RFC-0014-release-please-ruleset-bypass.md)                | release-please ruleset + bypass                                      | Accepted (name + §2a/§4 corrected by RFC-0021)                  | 2026-06-07 |
| [RFC-0015](RFC-0015-supply-chain-hardening-phase1.md)                | Supply-chain hardening (Phase 1): SHA-pin actions + SCA              | Implemented                                                     | 2026-06-07 |
| [RFC-0016](RFC-0016-otel-collector-validate-env.md)                  | Fix OTel Collector config validation                                 | Implemented                                                     | 2026-06-07 |
| [RFC-0017](RFC-0017-phase2-dx-and-combined-coverage.md)              | Phase 2: DX baseline + combined coverage                             | Implemented                                                     | 2026-06-07 |
| [RFC-0018](RFC-0018-phase3-org-migration-governance.md)              | Phase 3: org-migration governance                                    | Proposed (human-executed migration — not yet done)              | 2026-06-07 |
| [RFC-0019](RFC-0019-auto-merge-graceful-degradation.md)              | Auto-merge graceful degradation                                      | Accepted                                                        | 2026-06-07 |
| [RFC-0020](RFC-0020-phase2-extras-automerge-ratchet.md)              | Dependabot auto-merge + coverage ratchet                             | Implemented                                                     | 2026-06-07 |
| [RFC-0021](RFC-0021-ratify-main-ruleset-15-checks.md)                | Ratify enforced `main` ruleset (15 checks) + reconcile RFC-0013/0014 | Implemented (live apply via apply_branch_protection.sh — admin) | 2026-06-17 |

## Reconciliation items (from 2026-06-16 audit)

- ✅ **RFC-0013/0014 vs live ruleset (audit #326)** — resolved by **RFC-0021**: the enforced
  `main-branch-protection` set is ratified at **15 checks** (`Detect Secrets` restored as #15),
  `org-protection-ruleset.json` synced to the same set, and the name + RFC-0014 §2a/§4 contradiction
  corrected. **Remaining admin step:** run `scripts/governance/apply_branch_protection.sh` to apply
  the 15th check (`Detect Secrets`) live — until then `branch-protection-audit.yml` reports drift by
  design.
