# RFC-0018 — Phase 3: org migration to enforce CODEOWNERS reviews & dual-approval

> **Status:** Proposed (human-executed migration — see §6)
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** Repository Owner, Tech Lead, Security Lead
> **Related RFC:** RFC-0013 (branch protection), RFC-0014 (release-please bypass), RFC-0015 (Phase 1), RFC-0017 (Phase 2)
> **Related ADR:** ADR-0026 (SOX), ADR-0027 (ISO 27001), ADR-0015 (AI governance)
> **Change type:** Normal (governance / repository ownership)

---

## 1. Context

The repo documents strong segregation-of-duties controls (SOX ≥2 approvers, ISO 27001 CAB, AI
Governance dual sign-off for `src/guardrails/` & `hitl_gateway.py`) and ships an 89-line
`.github/CODEOWNERS` — but **none of it is enforced**:

- `.github/CODEOWNERS` references **7 `@your-org/<team>` placeholder teams** (`ai-governance`,
  `devops-team`, `platform-team`, `privacy-team`, `security-team`, `sre-team`, `tech-leads`) that
  **do not exist** — so GitHub can't require code-owner review.
- The repo is a **personal (user-owned)** namespace: no Teams, no `OrganizationAdmin`, and
  `RepositoryRole` bypass can't target the owner (proved in RFC-0014). So the `main-protection`
  ruleset runs with `required_approving_review_count: 0` and `require_code_owner_review: false`
  (RFC-0013), and releases still need `--admin`.

Net: the governance is **documentation, not enforcement** — an audit finding waiting to happen.
This RFC's decision realizes the design the repo was already built for.

## 2. Decision

**Migrate the repository to a GitHub organization, create the 7 Teams, and flip the ruleset to
enforce reviews.** Concretely (full steps in `docs/governance/org-migration-runbook.md`):

1. Create a GitHub **org**; create the **7 Teams** above and add members.
2. **Transfer** the repo into the org (GitHub auto-redirects the old URL).
3. Swap placeholders: `@your-org/` → `@<org>/` in CODEOWNERS and the few hardcoded
   `valdomirosouza` / `ghcr.io/valdomirosouza` / `github.com/valdomirosouza` references
   (`make template-init` already automates the `@your-org/` swap).
4. Apply the **post-migration ruleset** (`docs/governance/org-protection-ruleset.json`): same 9
   required checks + force-push/deletion block, **plus** `require_code_owner_review: true`,
   `required_approving_review_count: 1` (≥2 for SOX financial paths via team policy), and a
   **`OrganizationAdmin` bypass** (which finally lets the release-please PR merge without `--admin`).
5. Update RFC-0013/0014 status to the enforced model.

### 2a. Policy decision the owner must make (documented, not pre-decided)

Requiring human review **changes the docs auto-merge flow** (RFC-0003): a bot self-approval does
not satisfy a `require_code_owner_review` requirement. Options at migration time:

- **(Recommended) Enforce review, narrow auto-merge:** require 1 approval + code-owner review;
  retire docs auto-merge (or keep it only for a non-owned `docs/**`-only path via a separate,
  laxer ruleset). Maximizes governance integrity.
- **Keep auto-merge for docs:** scope `require_code_owner_review` via a path-targeted ruleset so
  `docs/**`-only PRs stay at 0 reviews while code/guardrail paths require owner review.

## 3. Alternatives Considered

| Option                                  | Pros                                                                       | Cons                                                       | Why rejected          |
| --------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------- | --------------------- |
| A (proposed) — migrate to org + enforce | Real SOX/ISO/AI dual-approval; fixes release bypass; Teams/CODEOWNERS work | One-time migration; URL/owner ref updates; review friction | —                     |
| Stay personal, soften the docs          | No migration                                                               | Abandons the controls the repo advertises                  | Governance regression |
| Stay personal, "best-effort" reviews    | No migration                                                               | Unenforceable; `--admin` per release persists              | The problem (#3/#6)   |

## 4. Impact

| Area          | Impact                                                                                                                                           |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Governance    | CODEOWNERS reviews + dual-approval **enforced** (SOX/ISO/AI)                                                                                     |
| Release flow  | `OrganizationAdmin` bypass → release PR merges without `--admin` (supersedes RFC-0014's PAT workaround, which can remain as belt-and-suspenders) |
| URLs / clones | Old `valdomirosouza/...` auto-redirects; GHCR images move to `ghcr.io/<org>/...`                                                                 |
| Auto-merge    | Changes per §2a decision                                                                                                                         |
| Contributors  | Need org membership + team assignment                                                                                                            |

## 5. Reference-update checklist (small blast radius)

Hardcoded `valdomirosouza` (excluding historical CHANGELOG/ADR/RFC records):
`README.md`, `CLAUDE_SESSION_INIT.md`, `.github/workflows/template-init.yml`,
`.github/workflows/template-sync.yml`, `docs/governance/owner-onboarding.md`,
`docs/quickstart/agent-onboarding.md`, `docs/compliance/iso27001-annex-a-control-matrix.md`,
`specs/system/SPEC-LGS-001-...md`. Plus `ghcr.io/valdomirosouza/*` image paths and
`github.com/valdomirosouza/Repository-Template-v2` URLs. (Git/API URLs auto-redirect; update for
correctness.)

## 6. Execution boundary (who does what)

**Human-only (account/ownership; cannot be automated by an agent):** create the org, create Teams +
add members, transfer the repo. **Agent-assistable (after the org exists):** apply the ruleset JSON,
run the placeholder/reference swaps, update RFC-0013/0014, verify. See the runbook.

## 7. Rollback

A transferred repo can be transferred back; rulesets can be deleted and the RFC-0013 personal-repo
ruleset re-applied. Plan a low-traffic window; announce the URL change.

---

_Approved by:_ _(signatures go here after CAB review)_
