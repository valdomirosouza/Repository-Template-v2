# RACI Matrix — Definition of Done & Governance

> **Version:** 1.0.0 | **Last updated:** 2026-06-06
> **Owner:** Tech Lead | **Approver:** Governance Council
> **ADR:** ADR-0052 | **Source:** agentic-sdlc-open-questions-resolved.md Q1

**Legend:** R = Responsible (does the work) · A = Accountable (owns the outcome) · C = Consulted (input required) · I = Informed (notified of outcome)

---

## Tier 1 — Defining & Governing the DoD

| Activity                                                                  | Product Owner | Tech Lead | Security Lead | SRE / Platform | Developer / Agent | Governance Council |
| ------------------------------------------------------------------------- | :-----------: | :-------: | :-----------: | :------------: | :---------------: | :----------------: |
| Author global DoD (`docs/process/DEFINITION_OF_DONE.md`)                  |       C       |   **R**   |       C       |       C        |         I         |         I          |
| Approve global DoD                                                        |       C       |     A     |     **R**     |       C        |         I         |       **A**        |
| Propose DoD change (PR to `docs/process/`)                                |       I       |   **R**   |       C       |       C        |         C         |         I          |
| Approve DoD change                                                        |       C       |     A     |     **R**     |       C        |         I         |       **A**        |
| Author per-service DoD addendum (`services/{name}/DEFINITION_OF_DONE.md`) |       C       |   **R**   |       C       |       C        |         I         |         I          |
| Approve per-service addendum                                              |       C       |   **A**   |       C       |       I        |         I         |         I          |
| Annual DoD review (align to ISO 27001 review cadence)                     |       C       |   **R**   |     **R**     |       C        |         I         |       **A**        |

---

## Tier 2 — Applying the DoD on Every Story / PR

| Activity                                     | Product Owner | Tech Lead | Security Lead | SRE / Platform | Developer / Agent |    CI / Automation    |
| -------------------------------------------- | :-----------: | :-------: | :-----------: | :------------: | :---------------: | :-------------------: |
| Complete DoD checklist in PR description     |       I       |     C     |       I       |       I        |       **R**       |           I           |
| Verify unit test coverage ≥ 80%              |       I       |     C     |       I       |       I        |       **R**       |   **R** (blocking)    |
| Verify security tests pass                   |       I       |     C     |     **R**     |       I        |         C         |   **R** (blocking)    |
| Verify abuse case tests pass                 |       I       |     C     |     **R**     |       I        |         C         |   **R** (blocking)    |
| Verify SBOM generated and attested           |       I       |     I     |       C       |     **R**      |         I         |   **R** (blocking)    |
| Verify OTel spans instrumented               |       I       |     C     |       I       |     **R**      |         C         | **R** (informational) |
| Verify K8s health probes configured          |       I       |     C     |       I       |     **R**      |         C         |   **R** (blocking)    |
| Verify CHANGELOG updated                     |       I       |   **R**   |       I       |       I        |       **R**       | **R** (informational) |
| Verify ADR created if architectural decision |       I       |   **A**   |       C       |       I        |       **R**       |           C           |
| Verify runbook updated if new failure mode   |       I       |     C     |       I       |     **A**      |       **R**       |           I           |
| Human code review approval                   |       C       |   **A**   |       C       |       I        |         C         |           I           |
| Mark story as Done in sprint board           |     **A**     |     C     |       I       |       I        |       **R**       |           I           |

---

## Tier 3 — Enforcement Escalation

| Scenario                                                         | Responsible           | Accountable        | Action                                                                           |
| ---------------------------------------------------------------- | --------------------- | ------------------ | -------------------------------------------------------------------------------- |
| PR merged without DoD checklist completion                       | Developer             | Tech Lead          | Revert PR; DoD retroactively applied before re-merge                             |
| CI gate bypassed (force-push to main)                            | CI / Automation alert | Tech Lead          | Automatic Issue opened; audit log entry; ADR-0026 SOX audit trail                |
| Security gate failure accepted without remediation               | Security Lead         | Governance Council | Security exception process: documented justification, time-bound mitigation plan |
| Per-service DoD relaxes a global gate                            | Tech Lead             | Governance Council | PR blocked by `governance-gate.yml`; escalation to council required              |
| Governance-council-approved label applied without council review | Governance Council    | CTO / CISO         | Label removed; PR re-blocked; council notified                                   |

---

## Tier 4 — Definition of Ready (DoR) RACI

| Activity                                                        | Product Owner | Tech Lead | Security Lead |         Developer / Agent          |
| --------------------------------------------------------------- | :-----------: | :-------: | :-----------: | :--------------------------------: |
| Write Problem Statement in Issue                                |     **R**     |     C     |       I       |                 I                  |
| Create Discovery Primer (`docs/product/FEAT-{id}/discovery.md`) |       C       |     C     |       I       |           **R** (agent)            |
| Review and approve Discovery Primer                             |     **A**     |   **R**   |       I       |                 I                  |
| Create NFR doc (`docs/product/FEAT-{id}/nfr.md`)                |       C       |     C     |       C       |           **R** (agent)            |
| Approve NFR doc                                                 |       I       |     C     |    **A/R**    |                 I                  |
| Write acceptance criteria (Gherkin)                             |       C       |     C     |       I       | **R** (agent draft → human refine) |
| Review acceptance criteria                                      |     **A**     |   **R**   |       I       |                 I                  |
| Apply DoR checklist (Grooming Ceremony)                         |       C       |  **A/R**  |       C       |                 I                  |

---

## Tier 5 — Definition of Release (DoR-Release) RACI

| Activity                                       | Release Manager | Tech Lead | Security Lead | SRE / Platform |   CI / Automation   |
| ---------------------------------------------- | :-------------: | :-------: | :-----------: | :------------: | :-----------------: |
| Verify all milestone Issues are `status: done` |      **R**      |     C     |       I       |       I        |          I          |
| Confirm chaos + model contract tests green     |        C        |   **R**   |       I       |       C        |        **R**        |
| Review SBOM and cosign attestation             |        C        |     I     |     **R**     |       C        |        **R**        |
| Review DAST (ZAP) scan report                  |        I        |     C     |    **A/R**    |       I        |          I          |
| PRR sign-off for new services                  |        C        |     C     |       C       |    **A/R**     |          I          |
| Apply `rc-approved` label                      |     **A/R**     |     C     |       C       |       I        |          I          |
| Tag GitHub Release and post notification       |      **R**      |     C     |       I       |       I        | **R** (CD pipeline) |

---

## File Structure for Per-Service Addenda

```
docs/process/
├── DEFINITION_OF_DONE.md      ← Global DoD (authoritative)
├── DEFINITION_OF_READY.md     ← Global DoR
├── DEFINITION_OF_RELEASE.md   ← Global DoR-Release
└── RACI.md                    ← This document

services/{name}/
└── DEFINITION_OF_DONE.md      ← Optional per-service addendum
    # Header must contain:
    # "This file EXTENDS docs/process/DEFINITION_OF_DONE.md.
    #  All global gates apply. Additional gates below:"
```
