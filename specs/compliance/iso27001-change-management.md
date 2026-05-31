# ISO 27001 A.12.1 Change Management — Specification

**ID:** SPEC-iso27001-change-management
**Version:** 1.0.0
**Status:** Approved
**Owner:** Tech Lead, DevOps Lead
**ADR:** ADR-0027

---

## 1. Purpose

Define the change management policy and procedure for all production system changes, satisfying ISO 27001 Annex A control A.12.1 (Operational Procedures and Responsibilities).

---

## 2. Change Classification Matrix

| Type      | Label              | CAB Required    | RFC Required      | Retroactive RFC | Deploy Window       |
| --------- | ------------------ | --------------- | ----------------- | --------------- | ------------------- |
| Standard  | `standard-change`  | No              | No                | No              | Mon–Thu 10:00–17:00 |
| Normal    | `normal-change`    | Yes (pre-merge) | Yes               | No              | Any, post-approval  |
| Emergency | `emergency-change` | Async TL+SecOps | Retroactive (24h) | Yes             | Immediate           |

Every production-impacting PR must carry exactly one of these three labels. The `cab-check` CI job blocks merge if no label is present.

---

## 3. Deploy Procedure Flowchart

```
Pre-deploy
  ├── PRR complete (prr-checklist.yaml all blocking items ✓)
  ├── Error budget > 10% (slo.yaml gate)
  ├── RFC_ID confirmed (for normal-change / emergency-change)
  └── DPIA/RIPD approved if new PII processing

Build
  ├── make build SERVICE=<name> VERSION=x.y.z
  ├── make sbom (CycloneDX SBOM generated)
  └── cosign sign + attest (SLSA provenance)

Staging validation
  ├── make deploy-staging SERVICE=<name>
  ├── Smoke tests (infrastructure/scripts/deploy/smoke-test.sh)
  ├── OWASP ZAP DAST scan (blocking — zero CRITICAL)
  └── Golden Signals check (error_rate < 1%, p99 < 500ms)

Canary production deploy
  ├── 5%  → 15min SLO observation → proceed or auto-rollback
  ├── 25% → 15min SLO observation → proceed or auto-rollback
  └── 100% → final Golden Signals confirmation

Change evidence
  └── Append entry to docs/change-log/YYYY-MM-DD.yaml
```

---

## 4. Rollback Procedure Flowchart

```
Trigger
  ├── Automated: SLO breach during canary (cd-production.yml rollback-on-failure job)
  └── Manual: on-call engineer executes make rollback SERVICE=<name>

Execute
  └── helm rollback <release> --wait --timeout 5m

Validate
  ├── make smoke-test (must pass on previous version)
  └── make golden-signals-check (error_rate below SLO threshold)

Record
  └── Append rollback entry to docs/change-log/YYYY-MM-DD.yaml
       Fields: timestamp, event=rollback, rfc_id, initiator, service,
               rolled_back_to, root_cause_preliminary, incident_ticket
```

RTO target: rollback complete within 1h (DORA MTTR Elite threshold, ADR-0028).
Runbook: `docs/runbooks/rollback-procedure.md`. HITL recovery: RB-003.

---

## 5. CAB Process Integration

Normal changes: RFC submitted via `docs/change-management/rfc/RFC-TEMPLATE.md`. CAB reviews RFC in weekly sync. Approval recorded as comment on PR; merge unblocked once `cab-check` CI job detects RFC label = APPROVED.

Emergency changes: TL and SecOps approve async in `#cab-emergency` Slack channel. Retroactive RFC created within 24h. Post-mortem mandatory (even if change was successful).

---

## 6. Configuration Item Scope

The following configuration item types are in scope for change management:

- Application code (all languages)
- Infrastructure as Code (Terraform, Helm charts, Kubernetes manifests)
- Secrets and encryption keys (rotation counts as Normal Change)
- Feature flags (`infrastructure/feature-flags/` — also requires ADR-0015 governance review)
- Database schema migrations (Alembic versions)
- CI/CD pipeline definitions (`.github/workflows/`)

---

## 7. Evidence Artifacts and Retention

| Artifact               | Location                                | Retention                          | Owner       |
| ---------------------- | --------------------------------------- | ---------------------------------- | ----------- |
| Per-deploy YAML record | `docs/change-log/`                      | 7 years (SOX), 3 years (ISO 27001) | DevOps Lead |
| RFC documents          | `docs/change-management/rfc/`           | 3 years                            | Tech Lead   |
| CAB meeting minutes    | `docs/governance/cab-minutes/`          | 3 years                            | DevOps Lead |
| SBOM per release       | GitHub Release artifacts + cold storage | 3 years                            | DevOps Lead |

---

## 8. Acceptance Criteria

- [ ] Every production PR carries exactly one change-type label; `cab-check` CI job validates this
- [ ] Normal-change PRs blocked until RFC_ID present in body and RFC status = APPROVED
- [ ] `docs/change-log/` contains an entry for every production deployment in the last 90 days
- [ ] End-to-end deploy + rollback achievable by following only the procedure in this spec
- [ ] Rollback completes within RTO (1h) as demonstrated in staging drill
