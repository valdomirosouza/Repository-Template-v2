# Release Evidence Package

> **Owner:** Tech Lead + DevOps Lead · **Status:** Living standard · **Last updated:** 2026-06-14
> Defines the single, auditable bundle of evidence every production release must produce. It makes
> the change-evidence rule in ISO 27001 (CLAUDE.md §11, ADR-0027) and — where applicable — SOX
> (CLAUDE.md §10, ADR-0026) operational by naming **what** is collected, **where** it lives, and
> **which gate** produces it. This closes the P0 "release evidence package" item of the repository
> improvement plan (Wave 10 — Governance).

## Why this exists

Each release already emits evidence across several systems (the change log, cosign attestations, the
SBOM, the DORA event). An auditor or incident responder should not have to reassemble that by hand.
This document is the **index** that ties those artefacts to one release, and the checklist that says a
release is not "done" until every piece exists.

## What a release must produce

Legend: ✓ automated by CI · ◐ semi-automated (CI emits, human confirms) · ✋ human-supplied.

| #   | Evidence item                                                                                          | Source of truth                                                | Produced by                                                            | Mode | Governing control                               |
| --- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- | ---------------------------------------------------------------------- | ---- | ----------------------------------------------- |
| 1   | **Change-evidence record** (deployer, RFC_ID, commit SHA, image digest, SBOM hash, timestamp, outcome) | `docs/change-log/YYYY-MM-DD.yaml`                              | `record-change-evidence` job (`cd-production.yml`)                     | ✓    | ISO 27001 A.12.1 (ADR-0027); SOX CC5 (ADR-0026) |
| 2   | **CAB / change approval** (RFC for normal/emergency change)                                            | RFC in `docs/change-management/rfc/` + commit `Refs: RFC-NNNN` | `cab-check` job                                                        | ◐    | ISO 27001 three-tier change (§11)               |
| 3   | **Signed container image** (keyless cosign signature + verified digest)                                | cosign attestation                                             | `verify-artifact` job                                                  | ✓    | OWASP A08; SLSA target (§7)                     |
| 4   | **SBOM** (CycloneDX) + its hash                                                                        | cosign SBOM attestation; `make sbom` locally                   | `verify-artifact` job (`sbom_hash` output)                             | ✓    | OWASP A06/A08; supply-chain (§7)                |
| 5   | **DAST attestation** (authenticated ZAP scan of this image)                                            | cosign `zap-dast/v1` attestation                               | `verify-artifact` (report mode during burn-in, ADR-0070)               | ◐    | OWASP A05/DAST gate (§7)                        |
| 6   | **SLO / error-budget canary result** (per-service thresholds met at 5→25→100%)                         | `docs/sre/slo/<service>.yaml` + canary job logs                | `load-slo` + `check-error-budget` + `promote-canary-*` jobs (ADR-0073) | ✓    | SRE / PRR (§12)                                 |
| 7   | **DORA deployment event** (lead time, deploy frequency provenance)                                     | Pushgateway → DORA dashboard                                   | `emit-dora-event` job (`dora_deployments_total`, ADR-0056)             | ✓    | DORA tracking (§12)                             |
| 8   | **Version consistency** (`version.txt` == `pyproject.toml`)                                            | `version.txt` (single source of truth, ADR-0057)               | `pr-governance` workflow                                               | ✓    | Release governance (§7.1)                       |
| 9   | **CHANGELOG entry** under the released version                                                         | `CHANGELOG.md`                                                 | `pr-governance` workflow                                               | ✓    | Quality gate (§3.5, §7.1)                       |
| 10  | **Rollback plan** (previous good version, runbook, RTO)                                                | `skills/change-management/deploy-rollback.md`; Runbook RB-003  | ✋ release owner                                                       | ✋   | ISO 27001 rollback (§11)                        |
| 11  | **PRR sign-off** (for a new service or major change)                                                   | PRR record                                                     | ✋ SRE Lead (`skills/sre/prr.md`)                                      | ✋   | Production readiness (§7)                       |

> Items 1, 3, 4, 6, 7 are emitted automatically by `cd-production.yml` — see the job names in the
> table. The package is the act of **confirming all eleven exist and linking them** to the release tag.

## The package: one file per release

Create `docs/governance/release-evidence/<version>.md` from the template below and attach it to the
GitHub Release. It is an **index of pointers**, not a copy of the evidence — link to the change-log
entry, the attestation, the DORA event, etc. Append-only, like the change log.

```text
# Release Evidence — v<MAJOR.MINOR.PATCH>

Release tag:      v_._._
Released by:      <github-actor>            Date: YYYY-MM-DD (UTC)
Change type:      standard | normal | emergency      RFC_ID: RFC-____ (omit for standard)
Commit SHA:       <sha>                      Image digest: sha256:____
SBOM hash:        sha256:____

Evidence index (must all resolve)
  [1]  Change-log entry .......... docs/change-log/YYYY-MM-DD.yaml#<service>
  [2]  CAB / RFC approval ........ docs/change-management/rfc/RFC-____.md   (or: standard-change, no RFC)
  [3]  Signed image ............. cosign verify ... (digest above)          → pass/fail
  [4]  SBOM attestation ......... sbom_hash above                           → pass/fail
  [5]  DAST attestation ......... zap-dast/v1 for this digest               → pass / report-mode (ADR-0070)
  [6]  Canary SLO result ........ docs/sre/slo/<service>.yaml; 5/25/100% met → pass/fail
  [7]  DORA event .............. dora_deployments_total emitted             → pass/fail
  [8]  Version consistency ...... version.txt == pyproject.toml             → pass
  [9]  CHANGELOG entry .......... CHANGELOG.md#v_._._                       → present
  [10] Rollback plan ............ previous good = v_._._; Runbook RB-003; RTO 3600s
  [11] PRR sign-off ............. <link or N/A — not a new service / major change>

Decision: RELEASED / HELD     Approver: <name, role>     Rationale: ...
```

## Retention

Mirror the change-log retention (`docs/change-log/SCHEMA.md`): **ISO 27001 A.12.1 → 3 years**;
**SOX CC5 (if SEC-listed) → 7 years**. The longer period applies when both frameworks are active.
Because the package only links to evidence, each linked artefact must itself satisfy the retention
above (the change-log YAML and attestations already do).

## Gaps & target state (not yet automated)

- **No generator yet.** The per-release index is assembled by hand from the CI job outputs. Target: a
  `record-change-evidence`-adjacent job (or `scripts/governance/`) that renders
  `docs/governance/release-evidence/<version>.md` from the same data it already writes to the change
  log, so the index is a build output rather than a manual step.
- **DAST is report-mode** during ADR-0070 burn-in (item 5). It blocks only after burn-in completes —
  track via `make burn-in-status`.
- **No `make verify-release-evidence`** linking-check yet — a follow-up could fail a release whose
  index has an unresolved pointer, the same way `verify-traceability` checks the service matrix.

---

## Related

- `docs/change-log/SCHEMA.md` — per-deploy evidence record (items 1) · ADR-0027, ADR-0026
- `.github/workflows/cd-production.yml` — jobs that emit items 1, 3, 4, 6, 7
- `skills/change-management/deploy-rollback.md` · Runbook RB-003 — item 10
- `skills/sre/prr.md` — item 11 · `docs/process/DEFINITION_OF_RELEASE.md` (Definition of Release)
- CLAUDE.md §7 (PR checklist), §10 (SOX), §11 (ISO 27001), §12 (DORA)
- ADR-0056 (DORA lead-time provenance) · ADR-0057 (version single source) · ADR-0070 (report-mode burn-in) · ADR-0073 (SLO-driven canary)
