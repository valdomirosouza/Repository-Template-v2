# Branch Protection as Code

> **Status:** Active · **Governing ADR:** [ADR-0071](../adr/ADR-0071-repository-settings-as-code.md) · **Owner:** DevOps Lead + Tech Lead

Branch-protection rulesets are **version-controlled source**, not UI clicks. The enforced gate
set lives in `.github/rulesets/*.json`, is applied by a human-run bootstrap script, and is
checked for drift on a schedule. A UI-only change to the protected gate set is a governance
bypass — this design makes it **visible (in `git`) and caught (by the audit)**.

## Why

The recurring failure mode this repo hit: gates were _documented_ but not _enforced_ — required
checks configured in the GitHub UI could be silently relaxed by an admin, with no diff, no
review, and no trace. Codifying the rulesets closes that gap:

- **Reviewable** — a change to what's enforced is a PR diff against `.github/rulesets/`.
- **Auditable** — the scheduled `Branch Protection Audit` workflow fails if live ≠ source.
- **Reproducible** — a fork or downstream adopter gets the same protection by running one script.

## Files

| File                                            | Role                                                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| `.github/rulesets/main.json`                    | Default-branch ruleset: PR + required status checks + no force-push/delete     |
| `.github/rulesets/develop.json`                 | Integration-branch ruleset (no PR rule, so `make sync-develop` ff still works) |
| `scripts/governance/apply_branch_protection.sh` | **Human-run** bootstrap (`gh api`); idempotent create/update; `--dry-run`      |
| `.github/workflows/branch-protection-audit.yml` | Scheduled + PR drift audit: fails if live rulesets diverge from source         |

## Applying (human admin step)

Applying rulesets needs **repo-admin scope** and changes access controls. Per CLAUDE.md §14 and
ADR-0071, **an AI agent must not run this** — it prepares the JSON and script only. A human with
admin runs:

```bash
scripts/governance/apply_branch_protection.sh --dry-run   # preview
scripts/governance/apply_branch_protection.sh             # apply
gh api repos/<owner>/<repo>/rulesets --jq '.[].name'      # verify
```

## Required-check selection — applicability-driven (the day-zero rule)

The required set in `main.json` lists only checks that **run on every PR** (the Python core +
the governance and security gates):

```
Governance Checks · Conventional PR title · GitHub Issue referenced · Spec reference ·
Version consistency · High-risk Action Guard (F7) · Lint · Unit Tests · Security Tests ·
CodeQL — Python · Contract Drift Check · Generate SBOM · DAST (OWASP ZAP baseline)
```

**Language-specific CIs (Java / Go / Frontend) are deliberately _not_ in the required set.** They
are **path-filtered** — a docs-only or Python-only PR never triggers `Java Lint & SAST`, so if it
were required GitHub would wait forever for a check that never reports and **block the merge**.
That is exactly the "consumer without Java/Go is blocked on day zero" failure ADR-0071 forbids.

To enforce a language CI as required **without** bricking unrelated PRs, adopt one of:

1. **Required-CI aggregator** — a single job that `needs:` the language jobs, runs
   `if: always()`, and reports success when every _non-skipped_ job passed. Require only that one
   aggregated context. Skipped (path-filtered) jobs don't block. _(Recommended follow-on — tracked
   in the strengthening plan; not part of the initial W1-T1 ruleset.)_
2. **Drop path-filtering** so the language job always runs (cheap-exit when no relevant files
   changed), then add its context to the required set.

Pick per your stack and add the contexts to `main.json` — the audit then keeps them honest.

## Day-zero property

A fresh clone has **zero** rulesets applied until a human runs the bootstrap. The repo therefore
ships _governable_ but not _self-locking_: an adopter chooses when to enforce, and against which
of their own check names. This preserves the template's day-zero usability while making the
intended protection one reviewed command away.

## Approval count on a personal repo (`required_approving_review_count: 0`)

`main-branch-protection` requires a PR but **0 approvals**, deliberately. On a **user-owned
(personal) repo**, an author cannot approve their own PR and **no `bypass_actors` type can target
the repo owner** (RFC-0014 §2a) — so any non-zero count would permanently block the solo owner from
merging their own work, including release-please PRs. The dual-approval / SOX intent of CLAUDE.md
§8/§10 is enforced two other ways instead:

1. **Governance-council label gate** (`governance-gate.yml`, a _required_ status check) — guardrail
   and agent paths (`src/guardrails/`, `src/agents/hitl_gateway.py`, `src/agents/hitl_store.py`) and
   autonomy flags cannot merge without the `governance-council-approved` (and, for autonomy,
   `legal-reviewed`) label. This works with 0 approvals and is the §8/§14.1 checkpoint here.
2. **Adopter step** — on an **org** repo with real teams, raise `required_approving_review_count`
   (≥ 2 for SOX) and set `require_code_owner_review: true` so the CODEOWNERS dual-reviewer rules
   bind. Replace the `@your-org/*` placeholders first.
