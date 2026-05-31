# ADR-0027 — ISO 27001 Change Management Integration

**Status:** Accepted
**Date:** 2026-05-31
**Authors:** Tech Lead, DevOps Lead
**Reviewers:** SRE Lead, Security Lead

---

## Context

ISO 27001 Annex A control A.12.1 (Operational Procedures and Responsibilities) requires formal change control for all production system changes. The repository currently has a deploy-rollback skill and RFC process, but lacks a formal three-tier classification system enforced at the CI/CD level. CAB approval is described in the release-check harness but is not validated programmatically by the production pipeline.

Without a machine-enforced change classification, the controls exist only as advisory documentation and cannot provide audit evidence for ISO 27001 certification.

---

## Decision

Implement a three-tier change classification enforced via GitHub PR labels and the `cd-production.yml` `cab-check` job:

| Tier             | Label              | CAB Required    | RFC Required      | Deploy Window          |
| ---------------- | ------------------ | --------------- | ----------------- | ---------------------- |
| Standard Change  | `standard-change`  | No              | No                | Mon–Thu 10:00–17:00    |
| Normal Change    | `normal-change`    | Yes (pre-merge) | Yes               | Anytime after approval |
| Emergency Change | `emergency-change` | Async TL+SecOps | Retroactive (24h) | Immediate              |

The `cab-check` job in `cd-production.yml` validates:

- PR has exactly one change-type label
- For `normal-change`: PR body or merge commit matches `Refs: RFC-\d+`
- For `emergency-change`: `EMERGENCY_APPROVED=true` env var set by TL+SecOps

Every production deployment records evidence in `docs/change-log/YYYY-MM-DD.yaml` (append-only): deployer, RFC_ID, image digest, SBOM hash, timestamp, outcome.

The `skills/change-management/deploy-rollback.md` skill governs the step-by-step procedure; this ADR governs the classification policy and enforcement mechanism.

---

## Consequences

- Normal changes require CAB review delay (typically 1–2 business days)
- Emergency change process requires documented retroactive RFC within 24h — enforced by monitoring
- `cd-production.yml` gains a blocking `cab-check` job before any canary deploy
- `docs/change-log/` becomes an append-only evidence directory; no files may be deleted or modified
- IaC changes (Terraform, Helm values, feature flags) are in scope — not just application code

---

## Alternatives Considered

**Advisory labels only (no CI enforcement)** — rejected because unenforceable controls provide no ISO 27001 audit evidence.

**Jira/ServiceNow integration** — valid for enterprises with existing ITSM tooling; deferred to adopting teams. The current approach uses GitHub labels as the CMDB lightweight equivalent.

**All changes as Normal (maximum gate)** — rejected as operationally burdensome for standard changes; three-tier classification matches ISO 27001 intent.
