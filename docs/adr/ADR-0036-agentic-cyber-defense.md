# ADR-0036: Agentic Cyber Defense Automation

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Skill:** `skills/devsecops/agentic-cyber-defense.md`
**Issue:** #9
**Related ADRs:** ADR-0029 (DevSecOps Pipeline Security), ADR-0034 (Escalation Protocol), ADR-0035 (AI-Assisted CI Review)

---

## Context

When a CI security gate (Bandit, SpotBugs, gosec, Trivy, OWASP dep-check) fails,
the current workflow is fully manual: a developer reads the raw tool output, determines
severity, decides whether to fix or accept risk, and (if HIGH/CRITICAL) manually opens
a GitHub Security Advisory. This process is inconsistent — advisory creation is often
skipped for time pressure, findings are inconsistently classified, and there is no
machine-readable record of finding-to-resolution lifecycle.

Gap 8.1 from the _2026 Agentic Coding Trends Report_ identifies automated agentic
cyber defense — operating at machine speed — as a mandatory capability for teams
where AI-generated code is entering production at high frequency.

The `security_finding_total` Prometheus metric was pre-emptively defined in Wave 3
(Issue #7, `src/observability/metrics.py`) to receive this data.

---

## Decision

Define `skills/devsecops/agentic-cyber-defense.md` as the authoritative protocol for
Claude Code to follow when any CI security gate fails. The skill specifies:

**1. Five-step automated response:**

- Parse tool output into the agent-readable finding format
- Classify by severity (`critical|high|medium|low`)
- Record `security_finding_total` Prometheus metric for every finding
- For HIGH/CRITICAL: create a GitHub Security Advisory draft via `gh api`
- Post a structured PR comment with normalised finding data and remediation guidance

**2. Agent-readable finding format** (JSON schema):
`tool`, `cve_id`, `severity`, `confidence`, `file`, `line`, `cwe`, `package`,
`installed_version`, `fixed_version`, `description`, `remediation`

**3. Merge gate rule:**
HIGH/CRITICAL findings without a mitigating ADR → `[HITL-ESCALATE]` (CLAUDE.md §14).
The agent must not proceed past this point without explicit Security Lead sign-off.

**4. Mitigating ADR lookup** before escalating: `grep -rn "{cve_id}" docs/adr/`.
If an existing ADR accepts the risk, reference it in the comment and proceed.

**5. Escalation decision tree** formalising when to block vs comment vs record-only.

---

## Consequences

**Positive:**

- Every HIGH/CRITICAL CI finding generates a GitHub Security Advisory draft
  automatically — no manual step required.
- The `security_finding_total` metric enables Grafana alerting on finding trends
  (e.g., "new HIGH finding in the last 24h" → page on-call).
- The normalised finding format makes findings machine-comparable across tools and PRs.
- The mitigating ADR lookup prevents unnecessary HITL escalations for known accepted risks.

**Neutral:**

- Advisory creation requires `security-events: write` permission on the token.
  The `ci-ai-review.yml` workflow uses `pull-requests: write` only; advisory creation
  must run in a separate step or job with elevated permissions.
- Medium and low findings are recorded in metrics but do not generate comments or
  advisories — intentional to avoid alert fatigue.

**Risk:**

- False positives from Trivy (unfixed CVEs with no available fix) will generate
  draft advisories that require manual triage. Mitigated by running Trivy with
  `--ignore-unfixed` as the default in `ci.yml` — only fixable CVEs are actionable.
- The skill requires the agent to have `gh` CLI access with repository-scoped token.
  In agentic sessions this is available; in autonomous pipelines the token must be
  explicitly granted via `GITHUB_TOKEN` with `security-events: write`.
