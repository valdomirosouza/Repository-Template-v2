# SLSA v1.0 — Supply-Chain Assessment

> Assesses the build/release pipeline against **SLSA v1.0** (Build track, L0–L3). The repo's
> stated target (glossary) is **SLSA Level 2+**. This sheet states the **actual** level today and
> the gap to the target. Status legend in [`README.md`](README.md).
>
> **Scope:** the container-image build/release path. **Last updated:** 2026-05-29.
> **Primary workflows:** `.github/workflows/release.yml`, `sbom.yml`, `cd-staging.yml`, `cd-production.yml`.

---

## Current level: **Build L2** (advancing to L3)

> **Update 2026-05-29 (REM-006, REM-007):** all 17 GitHub Actions are now **SHA-pinned** to commit
> digests, every workflow has a least-privilege top-level `permissions:` block, `release.yml` emits
> **signed SLSA build provenance** (`actions/attest-build-provenance`), and `ci.yml` runs a **Trivy**
> image CVE scan. The remaining L3 / OIDC items — OIDC registry/cloud auth, admission-time signature
> verification, and pinned `Syft`/`Cosign` installers — are tracked as **REM-011** (they require real
> cloud/cluster infrastructure). The per-row tables below describe the original assessment; rows
> attributed to REM-007 are now resolved except where noted REM-011.

| SLSA Build requirement                                                        | Level | Status     | Evidence / gap                                                                                                                                                                             |
| ----------------------------------------------------------------------------- | ----- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Scripted/automated build                                                      | L1    | ✅         | Build runs in GitHub Actions (`release.yml`, `cd-*.yml`) — no manual image builds.                                                                                                         |
| Provenance **exists**                                                         | L1    | 🟡 Partial | An **SBOM** (Syft, CycloneDX+SPDX) is produced and Cosign-attested — but a SLSA **build provenance** predicate (builder identity, inputs, params) is **not** generated. SBOM ≠ provenance. |
| Build runs on a **hosted** platform                                           | L2    | ✅         | GitHub-hosted runners.                                                                                                                                                                     |
| Provenance is **signed / authenticated**                                      | L2    | 🟡 Partial | Cosign **keyless** signing via OIDC (`id-token: write`) signs the image + SBOM attestation; once true SLSA provenance is emitted it must be signed the same way.                           |
| Provenance **distributed** with artifact                                      | L2    | 🟡 Partial | SBOM attached to GitHub Release; provenance not yet attached.                                                                                                                              |
| **Hardened**, isolated build; non-falsifiable provenance; ephemeral, isolated | L3    | ⏳ Not met | Several hardening gaps below.                                                                                                                                                              |

## Hardening gaps (block L2→L3, and weaken L1/L2)

| Gap                                                                            | Impact                                                                     | Remediation |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------- | ----------- |
| GitHub Actions pinned to **floating tags** (`@v4`, `@v5`) not commit SHAs      | A compromised/retagged action can alter the build → falsifiable provenance | **REM-007** |
| Most workflows lack least-privilege `permissions:` blocks                      | Over-broad `GITHUB_TOKEN` scope                                            | **REM-007** |
| `Syft`/`Cosign` installed via `curl … \| sh` without version/hash pinning      | Tool-supply-chain risk in the build itself                                 | **REM-007** |
| Registry auth uses **long-lived** `REGISTRY_USERNAME`/`PASSWORD` (not OIDC)    | Credential theft / rotation burden                                         | **REM-007** |
| No **container image CVE scan** (Trivy) in CI; PRR requires it                 | Vulnerable base layers can ship                                            | **REM-006** |
| No SLSA **provenance predicate** emitted (only SBOM attestation)               | Cannot prove _how/where_ built                                             | **REM-007** |
| No signature **verification at admission** (deploy trusts unsigned-equivalent) | Signing without verification is advisory                                   | **REM-007** |

## What's already strong

- **SBOM on every release + weekly** (`sbom.yml`), in two formats (CycloneDX + SPDX) via Syft.
- **Keyless artifact signing** (Cosign + Sigstore, OIDC-based) — no long-lived signing keys.
- **SBOM attestation** bound to the image digest.
- **Release-gate enforcement**: `harness/release-check.yml` blocks a release unless
  `sbom.cyclonedx.json` exists **and** its Cosign attestation verifies.
- **Multi-language dependency-vuln gating** in CI (pip-audit, govulncheck, OWASP Dependency-Check,
  pnpm audit) — strong dependency-layer integrity even though image-layer scanning is pending.

## Path to the stated target (L2+) and beyond

1. **Reach a clean L2** — emit a signed **SLSA provenance** predicate (e.g. the
   `slsa-framework/slsa-github-generator` or GitHub's built-in `actions/attest-build-provenance`),
   attach it to the release, and distribute alongside the image. _(REM-007)_
2. **Harden toward L3** — SHA-pin all actions, add least-privilege `permissions:`, replace
   `curl | sh` tool installs with pinned versions, and move registry/cloud auth to **OIDC**.
   _(REM-007)_
3. **Close the image layer** — add a Trivy (or Grype) image scan to CI and verify signatures at
   admission (e.g. Kyverno/Cosign policy) so signing becomes enforcing, not advisory. _(REM-006)_

All items are tracked in [`remediation-register.md`](remediation-register.md).
