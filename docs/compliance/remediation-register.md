# Remediation Register

> The single, prioritised backlog of control gaps surfaced by this compliance package and the
> [`specs/security/threat-model.md`](../../specs/security/threat-model.md). **REM-001…004 are
> owned by the threat model** (reproduced here for one consolidated view); **REM-005+ are new,
> surfaced by the ISO/SOC 2/SLSA assessment.** When an item lands, flip its row(s) in the
> [control matrix](iso27001-annex-a-control-matrix.md) to ✅ and mark this row Done.
>
> **Last updated:** 2026-05-29 · Owners reference `.github/CODEOWNERS` roles (currently placeholders — see REM-009).

## Priority legend

`P0` blocks any production handling of real data/customers · `P1` blocks enterprise engagement ·
`P2` required for certification (SOC 2 / ISO) · `P3` hygiene.

---

## Open items

| ID          | Severity      | Gap                                                                                                                                                                        | Why it matters (framework)                                                                                                             | Owner                  | Suggested target                                  |
| ----------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ------------------------------------------------- |
| **REM-001** | **P0**        | `/v1/hitl/{id}/decide` has **no operator authentication** — anyone reaching the endpoint can approve agent actions                                                         | The HITL control is the linchpin of the whole AI-governance model; unauth = impersonation. ISO 5.15/8.5, SOC 2 CC6.1                   | Security Lead          | **Immediately** — before any real-data deployment |
| **REM-005** | **P1 (High)** | `.github/workflows/auto-merge.yml` **auto-approves + merges** PRs, bypassing human review / CAB                                                                            | Breaks **segregation of duties / four-eyes** — a near-universal enterprise-questionnaire and audit item. ISO 5.3/8.4/8.32, SOC 2 CC8.1 | DevOps + Security Lead | **Before first enterprise engagement**            |
| **REM-009** | **P1**        | CODEOWNERS uses placeholder `@org/*` teams (don't resolve); DPIA is **Draft** (no DPO sign-off)                                                                            | Controls that name an owner who doesn't exist are not auditable; DPIA must be Approved for GDPR/LGPD. ISO 5.2/5.31                     | Tech Lead + DPO        | Before first enterprise engagement                |
| **REM-002** | P1            | `LLMTokenBudgetExceeded90Percent` alert not wired to PagerDuty                                                                                                             | Cost-exhaustion DoS goes unactioned. ISO 8.16 _(threat-model)_                                                                         | SRE Lead               | Next release                                      |
| **REM-003** | P1            | No **mTLS** between pods (Kafka/internal traffic plaintext)                                                                                                                | Lateral-movement / eavesdropping risk. ISO 5.14/8.20, SOC 2 CC6.7 _(threat-model)_                                                     | DevOps Lead            | Per ADR-0007 (service mesh)                       |
| **REM-006** | P2            | No **container image CVE scan** (Trivy) in CI — PRR requires it but it isn't wired                                                                                         | Vulnerable base layers can ship. ISO 8.7, SOC 2 CC6.8, SLSA                                                                            | DevSecOps              | Add to `ci.yml` / language CIs                    |
| **REM-007** | P2            | Supply-chain hardening: SHA-pin actions, add least-privilege `permissions:`, OIDC for registry/cloud auth, emit signed **SLSA provenance**, verify signatures at admission | Reaches the stated **SLSA L2+** target and removes falsifiable-build risk. ISO 5.21, SOC 2 CC9                                         | DevSecOps              | Toward SLSA L2→L3                                 |
| **REM-004** | P2            | DAST not run in `ci.yml` (OWASP ZAP runs only in `staging-check.yml`)                                                                                                      | Shift DAST left. ISO 8.29 _(threat-model)_                                                                                             | DevSecOps              | Next release                                      |
| **REM-008** | P2            | Enforcement gaps: `spec-compliance` gate is non-blocking; CHANGELOG / issue-link / Conventional-Commit not CI-enforced                                                     | Closes the "documented ≠ enforced" gap that auditors probe. ISO 5.36, SOC 2 CC5                                                        | Tech Lead              | Next release                                      |
| **REM-010** | P3            | `version.txt` (1.9.1) out of sync with `pyproject.toml` (1.15.0)                                                                                                           | Single-source-of-truth hygiene; release automation correctness                                                                         | DevOps Lead            | Next release                                      |

## Done

_None yet — this register is new (2026-05-29)._

---

## Notes on sequencing

- **REM-001 and REM-005 are the two that change a "yes/no" answer on an enterprise security
  questionnaire.** Do them first; they are also the two items the [control matrix](iso27001-annex-a-control-matrix.md)
  flags as 🟡 **Gap** rather than plain Partial.
- **REM-009 is a force-multiplier:** until the placeholder roles are real people and the DPIA is
  Approved, ~22 "Partial" controls cannot move to "Implemented" no matter what code lands.
- REM-006 + REM-007 are best done together (both touch the CI/release workflows) and together
  move SLSA from L1-partial to a clean L2.
