# RFC-0011 — Remove misplaced SBOM image-attestation from ci.yml & sbom.yml

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Security Lead
> **Related Issue:** #108
> **Related RFC:** RFC-0010 (GHCR publish via GITHUB_TOKEN) · **Related ADR:** ADR-0029 (DevSecOps)
> **Change type:** Normal

---

## 1. Context

RFC-0010 set the repo variable `CONTAINER_REGISTRY=ghcr.io` to enable image publishing in
`release.yml`. That had an **unintended side effect**: it activated previously-dormant
`if: vars.CONTAINER_REGISTRY != ''` "Attest SBOM to container image" steps in
`.github/workflows/ci.yml` (the `sbom` job) and `.github/workflows/sbom.yml`. Both now fail on
every push to `main`/`develop`:

```
Error: signing ghcr.io/valdomirosouza/Repository-Template-v2:<sha>:
could not parse reference: ... (could not parse reference)
```

Two defects in those steps:

1. **Mixed-case reference** — they use `${{ github.repository }}` (`valdomirosouza/Repository-Template-v2`); OCI references must be lowercase, so cosign rejects the string outright.
2. **No image to attest** — `ci.yml` builds with `push: false` (load-only, for Trivy) and `sbom.yml` builds nothing. Neither pushes an image, so there is nothing at `<registry>/<repo>:<sha>` to attest even after lowercasing.

Only `release.yml` builds **and pushes** a container image, and it already attests that image's
SBOM correctly (lowercased, RFC-0010). PR runs are unaffected (these steps are push-only), so
the failure reddens branch CI on `main`/`develop` without blocking PR merges.

## 2. Proposed Change

**Remove the "Attest SBOM to container image" steps** (and the now-unused cosign install /
registry login / `REGISTRY_USERNAME`/`REGISTRY_PASSWORD` env / `packages: write` permission)
from both workflows. Keep SBOM **generation + validation + artifact upload** — the real value
of these workflows (a supply-chain inventory on every main push and weekly).

- `ci.yml` (`sbom` job): drop "Install Cosign" + "Attest SBOM to container image"; keep
  generate → validate → upload.
- `sbom.yml`: drop login, cosign install, attest; rename to **"SBOM — Generate"**; add the same
  empty-SBOM validation; keep generate (CycloneDX + SPDX) → upload.

Image-level SBOM **attestation remains in `release.yml`** — the only workflow that builds and
pushes an image, where attestation is meaningful and the reference is lowercased (RFC-0010).

## 3. Alternatives Considered

| Option                                           | Pros                                                         | Cons                                                             | Why rejected               |
| ------------------------------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------------- | -------------------------- |
| A (proposed) — remove the misplaced attest steps | Fixes the failure at its root; SBOM still generated/retained | Loses a (non-functional) attest step                             | —                          |
| B — lowercase the ref in ci/sbom (like RFC-0010) | Smaller diff                                                 | Still fails: **no image is pushed** in ci/sbom to attest against | Doesn't fix the real cause |
| C — make ci/sbom build+push a per-commit image   | "Real" attestation                                           | Heavy; per-commit images pollute GHCR; duplicates release.yml    | Wrong place; cost/noise    |
| D — unset `CONTAINER_REGISTRY`                   | One-line                                                     | Re-breaks release.yml publishing (reverts RFC-0010)              | Loses desired capability   |

## 4. Impact Assessment

| Area                    | Impact           | Notes                                                                                                                      |
| ----------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------- |
| API / DB / PII          | None             | CI/release tooling only                                                                                                    |
| Security / supply chain | Neutral→positive | SBOM still generated/validated/retained on every main push + weekly; image attestation still happens at release (ADR-0029) |
| Branch CI               | Positive         | `main`/`develop` push CI goes green again                                                                                  |
| `release.yml`           | None             | Unchanged; still builds + attests the released image                                                                       |
| `cd-staging.yml`        | None             | Already lowercases its ref and is deploy-gated; not affected                                                               |

## 5. Rollout Plan

1. Merge after DevOps/Security review (touches `.github/workflows/` → human review).
2. Next push to `main`/`develop`: the `SBOM — Generate` workflow and CI `Generate SBOM` job
   complete green (generate + validate + upload; no attest).
3. Smoke test: confirm no `could not parse reference` error and that the SBOM artifact is uploaded.

## 6. Rollback Plan

Revert this PR — restores the prior (failing) attest steps. No data or irreversible state.

## 7. Timeline

| Milestone                        | Target date |
| -------------------------------- | ----------- |
| RFC approved                     | 2026-06-07  |
| Implementation complete          | 2026-06-07  |
| Verified green on next main push | on merge    |

## 8. Open Questions

- [ ] Optional follow-up: cosign **sign-blob** the SBOM artifact (keyless) for tamper-evidence without needing an image. Out of scope here.

---

_Approved by:_ _(signatures go here after CAB review)_
