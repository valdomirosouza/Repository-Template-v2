# Governance Labels

**Owner:** AI Governance Lead + General Counsel
**Issue:** #14 | **ADR:** ADR-0037

These two GitHub labels gate merges of PRs that affect agent autonomy controls.
They must be applied by the designated approver — not self-applied by the PR author.

---

## Labels

### `governance-council-approved` (red — #e11d48)

**Applied by:** COO or CISO after cross-functional governance council review.

**Required when a PR touches:**

- `infrastructure/feature-flags/flags/autonomous-mode*.yaml`
- `infrastructure/feature-flags/flags/autonomy-tier-ready.yaml`
- `src/agents/hitl_gateway.py`

**What the council reviews:**

- Is the autonomy level change justified by the current maturity assessment?
- Are all Autonomy-tier prerequisites met (Learn stage, context graph)?
- Has the risk impact on HITL coverage been evaluated?
- Is the change within the approved FinOps budget (ADR-0020)?

**Council composition:** COO, CFO (budget impact), CISO, AI Governance Lead, General Counsel.
Meeting cadence: monthly standing meeting; emergency session within 48h for P0 changes.

---

### `legal-reviewed` (purple — #7c3aed)

**Applied by:** General Counsel or designated Deputy after legal/compliance review.

**Required when a PR touches:** (same paths as above)

**What legal reviews:**

- GDPR/LGPD compliance impact of increased agent autonomy
- EU AI Act risk category change (if applicable)
- Data processing agreement coverage for any new tool integrations
- Liability exposure from reduced HITL supervision

---

## Approval Workflow

```
1. PR author opens PR targeting main with autonomy-affecting changes
2. governance-gate CI check runs → fails with instructions
3. PR author notifies AI Governance Lead
4. AI Governance Lead schedules council review (or async if minor change)
5. COO/CISO applies governance-council-approved after council sign-off
6. General Counsel applies legal-reviewed after compliance review
7. governance-gate CI check re-runs → passes
8. Normal PR review and merge proceeds
```

**Escalation:** If council review takes >5 business days, the SRE Lead may request
an emergency governance session. Document the reason in the PR body.

---

## Informational Changes (gate is advisory, not blocking)

If the PR only changes a flag's _description_ or _metadata_ (not its enabled/disabled
default value), the `governance-gate` workflow runs in informational mode and will not
block the merge. The labels are still recommended but not required.

---

## Related

- `docs/adr/ADR-0037-governance-gate-enforcement.md`
- `docs/adr/ADR-0015-feature-flag-strategy.md`
- `.github/workflows/governance-gate.yml`
