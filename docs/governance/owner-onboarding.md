# Owner Onboarding — Assigning Real Code Owners

> REM-009 · ISO 5.2 / 5.31 · SOC 2 CC5.2
>
> This guide is for the team **adopting this template**. Complete it before your first
> enterprise engagement or SOC 2 / ISO 27001 audit. Every step here closes a "Partial"
> row in `docs/compliance/iso27001-annex-a-control-matrix.md`.

---

## Why this matters

`.github/CODEOWNERS` gates who must review PRs touching critical paths (security, privacy,
AI governance, infrastructure). If a reviewer listed in CODEOWNERS doesn't exist on GitHub,
the auto-assignment silently fails and consequential changes can merge without the required
review — undermining segregation of duties (ISO 5.3 / SOC 2 CC8.1).

A CI gate in `.github/workflows/ci.yml` (`governance` job step
`Validate CODEOWNERS has no @org/ placeholder teams`) will fail the build if any `@org/`
patterns remain. This PR cannot pass CI until CODEOWNERS is correct.

---

## Step 1 — Create a GitHub Organisation (if not already done)

If you're deploying from a personal fork, create a GitHub Org for your company:

```
https://github.com/organizations/new
```

Move the repo to the org or fork it under the org. Using org teams gives you:

- Centralized access management (add/remove team members once, not per-repo)
- Audit-trail of who approved what
- Automated reviewer rotation via team maintainers

---

## Step 2 — Create the required GitHub Teams

For each role in the table below, create a GitHub Team under your org with at least one real
member. Navigate to: `https://github.com/orgs/<your-org>/teams/new`

| Role slug in CODEOWNERS        | Suggested team name  | Minimum members     | ISO/SOC 2 requirement              |
| ------------------------------ | -------------------- | ------------------- | ---------------------------------- |
| `@your-org/tech-lead`          | `tech-lead`          | 1                   | ISO 5.2 (roles & responsibilities) |
| `@your-org/dpo`                | `dpo`                | 1 (must be the DPO) | ISO 5.31, GDPR Art. 37             |
| `@your-org/security-lead`      | `security-lead`      | 1                   | SOC 2 CC5.2, ISO 5.2               |
| `@your-org/ai-governance-lead` | `ai-governance-lead` | 1                   | EU AI Act Art. 22, ISO 5.2         |
| `@your-org/sre-lead`           | `sre-lead`           | 1                   | SOC 2 A1.1 (availability)          |
| `@your-org/devops-lead`        | `devops-lead`        | 1                   | SOC 2 CC8.1                        |
| `@your-org/engineering-team`   | `engineering-team`   | All engineers       | ISO 5.2                            |

> **Note on segregation of duties:** The HITL gateway (`src/agents/hitl_gateway.py`) requires
> two distinct approvers. `security-lead` and `ai-governance-lead` must be different individuals
> or teams. A single person in both roles satisfies the letter of the CODEOWNERS rule but not
> the intent of ISO 5.3 segregation of duties.

---

## Step 3 — Update CODEOWNERS

Edit `.github/CODEOWNERS` and replace each `@valdomirosouza` entry with the appropriate
`@your-org/team-name`. Example for the global fallback and governance paths:

```
# Before (template default)
*                       @valdomirosouza
docs/adr/               @valdomirosouza

# After (your organisation)
*                       @your-org/engineering-team
docs/adr/               @your-org/tech-lead
```

Replace **every** occurrence. The CI gate `Validate CODEOWNERS has no @org/ placeholder teams`
will catch any missed `@org/` strings — make sure there are none.

---

## Step 4 — Configure branch protection

In GitHub: **Settings → Branches → Branch protection rules → main**

Required settings:

- [x] Require a pull request before merging
- [x] Require approvals: **1** (minimum; recommend 2 for critical paths)
- [x] Require review from Code Owners ← **this is what activates CODEOWNERS**
- [x] Require status checks to pass (select all 9 required checks)
- [x] Require branches to be up to date before merging (strict mode)
- [x] Restrict who can push to matching branches

Verify by opening a test PR that touches `src/agents/hitl_gateway.py` — both
`@your-org/security-lead` and `@your-org/ai-governance-lead` should be auto-requested.

---

## Step 5 — DPIA sign-off (DPO required)

The DPIA at `docs/privacy/dpia/dpia-v1.md` is Draft until the DPO completes Section 5.
The DPO must:

1. Review Section 3 (Risk Assessment) — confirm all risks are correctly rated
2. Review Section 4 (Measures) — confirm technical and organisational measures are in place
3. Complete Section 5 (Consultation and Approval) — sign with name and date

Under GDPR Art. 36 the DPO must also determine whether supervisory-authority consultation
is required. For this system the residual risks are Low — consultation is not required
unless a national DPA has issued guidance requiring it for AI systems.

**Until the DPIA is Approved:**

- ISO 5.31 (legal requirements) remains 🟡 Partial
- Processing activities should be considered unvalidated for regulatory purposes

---

## Step 6 — Verify in the ISO control matrix

After completing Steps 1–5, update `docs/compliance/iso27001-annex-a-control-matrix.md`:

| Control                                             | Before     | After          |
| --------------------------------------------------- | ---------- | -------------- |
| 5.2 — Information security roles & responsibilities | 🟡 Partial | ✅ Implemented |
| 5.3 — Segregation of duties                         | 🟡 Partial | ✅ Implemented |
| 5.18 — Access rights                                | 🟡 Partial | ✅ Implemented |
| 5.31 — Legal, statutory, regulatory requirements    | 🟡 Partial | ✅ Implemented |

---

## Checklist summary

```
[ ] GitHub Org created (or repo already under an org)
[ ] All 7 teams created with at least one real member each
[ ] CODEOWNERS updated — no @org/ patterns remaining
[ ] CI governance job passes (no @org/ validation error)
[ ] Branch protection configured with "Require review from Code Owners"
[ ] Test PR confirms auto-assignment works for hitl_gateway.py dual-approval
[ ] DPO has reviewed and signed dpia-v1.md Section 5
[ ] DPIA status updated from Draft → Approved
[ ] ISO control matrix 5.2, 5.3, 5.18, 5.31 updated to ✅ Implemented
[ ] REM-009 moved to Done in remediation-register.md
```
