# ADR-0056 — Release Hardening: CAB-Gated Deploy, DORA Lead-Time Provenance & Artifact Integrity Verification

**Status:** Accepted
**Date:** 2026-06-06
**Authors:** Valdomiro Souza

---

## Context

An audit of the production deploy workflow (`.github/workflows/cd-production.yml`)
against the _Agentic SDLC Repository Improvement Directive_ (§5) found three
release-governance gaps where the documented control existed but was not actually
enforced:

- **P0-5 — CAB check did not block deployment.** The `cab-check` job validated the
  change-type label and RFC/CAB approval, but `deploy-canary` only depended on
  `check-error-budget`. CAB validation ran in parallel and could fail without
  stopping the rollout — the control was advisory, not blocking.

- **P1-5 — DORA lead time silently reset to zero.** This workflow is triggered only
  by `workflow_dispatch`, yet `emit-dora-event` read
  `github.event.pull_request.number` (always empty here) and fell back to "now",
  yielding a ~0 lead time. The Elite DORA metric was being silently fabricated.

- **P1-6 — No artifact integrity verification before deploy.** The rollout
  referenced a mutable image tag and never verified the Cosign signature, SBOM
  attestation, or SLSA provenance before shifting production traffic. A tampered or
  unsigned image could be deployed.

## Decision

Harden the production workflow so each control is enforced, not merely present.

### P0-5 — CAB blocks deployment

`deploy-canary` now declares:

```yaml
needs: [cab-check, check-error-budget, verify-artifact]
```

No production traffic shifts unless change governance, error budget, and artifact
integrity all pass. `cab-check` is also refined to distinguish change types:

- **standard-change** — pre-approved, no extra evidence.
- **normal-change** — requires `Refs: RFC-NNNN` **and** `MANUAL_APPROVAL=confirmed`
  (set after CAB approves the RFC).
- **emergency-change** — requires emergency evidence in the PR body: an incident
  reference (`Incident: INC-NNNN`) **and** `Emergency-Approval: <approver>`
  (TL + SecOps async approval; retroactive RFC within 24h per CLAUDE.md §11).

### P1-5 — DORA lead-time provenance

`emit-dora-event` no longer reads PR context. It checks out full history + tags and
resolves the reference timestamp from the version tag (`v{version}` or `{version}`).
The lead time is computed **only** when a real reference exists. When it cannot be
resolved, the job records `source=workflow_dispatch` and emits a
`dora_lead_time_source` gauge **without** a `dora_lead_time_seconds` value — an
unknown lead time is never reported as zero. The `lead_time_source` is also written
to the change-evidence record.

### P1-6 — Artifact integrity verification

A new blocking `verify-artifact` job (between `cab-check` and `deploy-canary`):

1. Resolves the **immutable digest** from the tag (`crane digest`).
2. Verifies the **Cosign signature** (keyless) — blocking.
3. Verifies the **SBOM attestation** (CycloneDX) and records its SHA-256 hash.
4. Verifies **SLSA provenance**.
5. Exposes `image_digest` and `sbom_hash` as job outputs.

`deploy-canary` deploys the verified digest (`--set image.digest=...`), not the
mutable tag. `record-change-evidence` consumes the verified outputs and now captures
the full provenance chain: version, commit SHA, image digest, SBOM hash, lead-time
source, timestamp, and deployer.

cosign and crane are installed from pinned release binaries; verification identity
and OIDC issuer are configurable via repo variables with GitHub-Actions defaults.

## Consequences

### Positive

- A failed CAB check, error-budget check, or artifact verification now hard-stops the deploy.
- DORA lead time is honest: real value from the version tag, or an explicit `workflow_dispatch` provenance marker — never a fabricated zero.
- Production runs only verified, signed, attested images, pinned to an immutable digest.
- Change evidence is audit-complete (ISO 27001 A.12.1 / SOX CC5): version, SHA, digest, SBOM hash, lead-time source, timestamp, deployer.
- The governance properties are locked by `tests/unit/process/test_cd_production_workflow.py`, so they cannot silently regress.

### Negative / Trade-offs

- The deploy now requires the image to be Cosign-signed with SBOM + provenance attestations — a fork must wire its build pipeline (and identity/issuer variables) accordingly or the verify job fails (intended fail-closed).
- `verify-artifact` adds a step and ~1 job of latency before canary; acceptable for a production gate.
- Lead time is measured from the version tag commit, not the PR's first commit. For tag-per-release flows this is accurate; teams wanting first-commit lead time must add tag annotations or a richer resolver.

### Neutral

- The helm chart must honor `image.digest`; the value is passed alongside `image.tag`.
- cosign/crane are installed via pinned release binaries rather than marketplace actions, avoiding action-SHA pinning churn (checksum pinning is a possible future hardening).

## Alternatives Considered

**Keep cab-check parallel and rely on branch protection:** Rejected — branch
protection governs merges, not the dispatch-time deploy. The job dependency is the
only thing that blocks the rollout itself.

**Compute lead time from the first PR commit via the API:** Rejected for the
dispatch path — there is no PR context. The version tag is the reliable anchor for a
manually dispatched release; absence is recorded honestly rather than guessed.

**Verify only the Cosign signature:** Rejected — signature proves origin but not
contents/build. Verifying SBOM and SLSA provenance closes the supply-chain gap
(A06/A08) the directive calls out.

---

## References

- ADR-0027 — ISO 27001 change management
- ADR-0026 — SOX controls (change evidence)
- ADR-0028 — DORA metrics
- CLAUDE.md §11 (ISO 27001 change classes), §12 (DORA)
- `docs/change-log/SCHEMA.md` — change evidence schema
- Directive: `Agentic-SDLC-Repository-Improvement-Directive.md` §5 (P0-5, P1-5, P1-6)
- Issue: #46
