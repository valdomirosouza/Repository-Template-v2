# RFC-0021 — Ratify the enforced `main` ruleset (15 required checks) and reconcile RFC-0013/0014

> **Status:** Implemented (source-of-truth; live apply via `scripts/governance/apply_branch_protection.sh` — admin step)
> **Date:** 2026-06-17
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/`), Security Lead, Tech Lead
> **Related RFC:** RFC-0013 (branch protection main), RFC-0014 (ruleset/bypass), RFC-0018 (org migration)
> **Related ADR:** ADR-0027 (ISO 27001 change mgmt), ADR-0071 (settings-as-code)
> **Change type:** Normal

---

## 1. Context

The 2026-06-16 ADR/RFC audit (#326) found the **enforced** `main` ruleset had diverged from the
RFCs that designed it, with **no superseding RFC**:

| Aspect                    | RFC-0013/0014 (as written)                          | Live `.github/rulesets/main.json` (as enforced)            |
| ------------------------- | --------------------------------------------------- | ---------------------------------------------------------- |
| Ruleset name              | `main-protection`                                   | `main-branch-protection`                                   |
| Required checks           | 9 (DAST/SBOM/Integration excluded as "flaky infra") | 14 (incl. DAST, SBOM, CodeQL, Security Tests, F7, council) |
| `Detect Secrets` required | yes                                                 | **no**                                                     |
| `bypass_actors`           | RFC-0014 §4 ships one (contradicting its own §2a)   | none                                                       |

Two sources of truth also disagreed: `docs/governance/org-protection-ruleset.json` (the RFC-0018
post-org-migration ruleset) still encoded the **old 9-check** set, so migrating to an org would
**silently drop** DAST/SBOM/CodeQL/F7/council enforcement.

The live 14-check set is **stricter and better** than the RFC-0013 design — RFC-0013 excluded
DAST/SBOM/Integration only to avoid flaky-infra blocking, but those jobs have since stabilised.
The right fix is to **ratify reality forward**, not revert.

## 2. Decision

1. **Ratify the enforced set, now 15 checks.** Adopt the live 14-check set as canonical and **add
   `Detect Secrets`** as the 15th required check — secret scanning genuinely should gate `main`
   (restores the RFC-0013/0014 intent). `Detect Secrets` is the exact check-run name produced by
   `.github/workflows/secret-scanning.yml`, so it is safe to require.
2. **Canonical name is `main-branch-protection`** (the live name). RFC-0013/0014's `main-protection`
   wording is superseded by this RFC.
3. **No bypass actor on the personal-repo ruleset** — confirms RFC-0014 §2a; the contradictory
   §4 `bypass_actors` block is void (and was never live).
4. **Single source of truth.** `docs/governance/org-protection-ruleset.json` (RFC-0018, org-level)
   is synced to the same 15-check set; it keeps its intentional extras (code-owner review,
   1 approval, OrganizationAdmin bypass for release-please) but no longer drops checks on migration.
5. **Apply is an admin step (ADR-0071).** Editing `main.json` is the source-of-truth change; a
   human admin runs `scripts/governance/apply_branch_protection.sh` to apply it live. Until applied,
   `branch-protection-audit.yml` will report drift (warning on PRs, failure on the scheduled run) —
   that is the intended "apply me" signal.

## 3. Alternatives Considered

| Option                                                 | Why rejected                                                                            |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| Revert the live ruleset to the RFC-0013 9-check design | Weakens enforcement (drops DAST/SBOM/CodeQL/F7/council); those jobs are no longer flaky |
| Ratify 14 checks as-is, leave `Detect Secrets` ungated | Leaves the secret-scanning gate the RFCs explicitly wanted off `main`                   |
| Leave the divergence undocumented                      | The reason this RFC exists — "we have a ruleset" must match what is enforced            |

## 4. Impact

| Area          | Impact                                                                            |
| ------------- | --------------------------------------------------------------------------------- |
| Enforcement   | +1 required check (`Detect Secrets`); stricter, matches security intent           |
| Org migration | `org-protection-ruleset.json` now mirrors the canonical set — no silent weakening |
| Live apply    | Requires one admin run of `apply_branch_protection.sh`; PR-time audit only warns  |
| Docs          | RFC-0013/0014 carry correction notes pointing here; RFC index updated             |

## 5. Rollout / Rollback

1. Merge this PR (source-of-truth: `main.json` 15 checks, org file synced, correction notes).
2. **Admin:** run `scripts/governance/apply_branch_protection.sh` to apply the 15-check ruleset live;
   verify with `gh api repos/<repo>/rulesets`.
3. Confirm the next PR shows `Detect Secrets` as a required check.

Rollback: revert this PR and re-run `apply_branch_protection.sh` (restores the 14-check live set).

## 6. Governance

Per ADR-0027 this is a `normal-change`; HITL approval is the repo owner approving this PR. Resolves
audit issue #326, including RFC-0014's internal §2a/§4 contradiction.

---

_Approved by:_ _(repo owner — see PR approval)_
