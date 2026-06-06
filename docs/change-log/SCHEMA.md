# Change Log Schema

The `docs/change-log/` directory stores per-deploy YAML evidence records required by
ISO 27001 A.12.1 (ADR-0027) and, where applicable, SOX CC5 (ADR-0026).

Files are named `YYYY-MM-DD.yaml` and are **append-only** — no existing entry may be
modified or deleted. Each file contains a YAML list of deployment and rollback events
for that calendar date.

---

## Deployment Event Schema

```yaml
- timestamp: "2026-05-31T14:00:00Z" # ISO-8601 UTC — required
  event: deploy # deploy | rollback — required
  rfc_id: "RFC-0042" # required for normal-change and emergency-change; omit for standard-change
  deployer: "github-actor-login" # GitHub Actions actor — required
  service: "api-gateway" # service name from services.yaml — required
  version: "1.18.0" # SemVer — required
  commit_sha: "abc123def456..." # git SHA deployed — required (ADR-0056)
  image_digest: "sha256:abc123..." # full SHA-256 digest of the verified, signed container image — required
  sbom_hash: "sha256:def456..." # SHA-256 of the verified CycloneDX SBOM attestation — required
  lead_time_source: "version_tag" # version_tag | workflow_dispatch — DORA lead-time provenance (ADR-0056)
  environment: "production" # production | staging — required
  change_type: "normal-change" # standard-change | normal-change | emergency-change — required
  outcome: "success" # success | rollback | failure — required
  notes: "" # optional free-text
```

## Rollback Event Schema

```yaml
- timestamp: "2026-05-31T15:30:00Z" # ISO-8601 UTC — required
  event: rollback # required
  rfc_id: "RFC-0042-ROLLBACK" # required
  initiator: "github-actor-login" # required
  service: "api-gateway" # required
  rolled_back_to: "1.17.9" # version restored — required
  root_cause_preliminary: "Elevated 5xx error rate at 5% canary" # one line, within 1h — required
  incident_ticket: "INC-0123" # incident tracker reference — required
  environment: "production" # required
```

---

## Retention

| Compliance framework    | Minimum retention |
| ----------------------- | ----------------- |
| ISO 27001 A.12.1        | 3 years           |
| SOX CC5 (if applicable) | 7 years           |

The longer retention period applies when both frameworks are active.

---

## Automation

The `record-change-evidence` job in `.github/workflows/cd-production.yml` appends entries
automatically after every deploy or rollback. Manual entries must follow this schema exactly.
