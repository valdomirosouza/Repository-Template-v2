# RFC-0010 — Publish release images to GHCR via the built-in GITHUB_TOKEN

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Release Manager, Security Lead
> **Related Issue:** #96
> **Related RFC:** RFC-0009 (graceful skip) · **Related ADR:** ADR-0029 (DevSecOps), ADR-0059 (progressive adoption)
> **Change type:** Normal

---

## 1. Context

`build-release-image` (release.yml) required `CONTAINER_REGISTRY` + `REGISTRY_USERNAME` +
`REGISTRY_PASSWORD` — none configured (#96), so image publish couldn't run (RFC-0009 now skips
it gracefully). Configuring an external registry means storing credentials; the cleanest
zero-secret option for a GitHub-hosted repo is **GHCR (ghcr.io) authenticated with the built-in
`GITHUB_TOKEN`**, which `release.yml` already grants (`packages: write`, `id-token: write`,
`attestations: write`).

## 2. Proposed Change

1. **Set the repo variable `CONTAINER_REGISTRY = ghcr.io`** (done out-of-band; not a secret) so
   the RFC-0009 guard enables `build-release-image`.
2. **Authenticate with `GITHUB_TOKEN`** instead of stored secrets:
   ```yaml
   with:
     registry: ${{ vars.CONTAINER_REGISTRY }}
     username: ${{ github.actor }}
     password: ${{ secrets.GITHUB_TOKEN }}
   ```
3. **Lowercase the image name.** GHCR/OCI require lowercase repository names, but
   `github.repository` is `valdomirosouza/Repository-Template-v2` (mixed case). A new step
   computes `name=<registry>/<repo>` via `tr '[:upper:]' '[:lower:]'` (POSIX-portable; not the
   bash-4 `${VAR,,}`), and all tags / SLSA subject / cosign targets use `steps.img.outputs.name`
   → `ghcr.io/valdomirosouza/repository-template-v2`.
4. **`cosign sign|attest --yes`.** Add `--yes` for non-interactive keyless signing in CI (OIDC
   via `id-token: write`); without it cosign would prompt and hang/fail — a latent bug in the
   prior steps that never ran because login failed first.

## 3. Alternatives Considered

| Option                                     | Pros                                                                      | Cons                                                                               | Why rejected                         |
| ------------------------------------------ | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------ |
| A (proposed) — GHCR + GITHUB_TOKEN         | Zero stored secrets; works on any fork; keyless signing; native to GitHub | Tied to GHCR                                                                       | —                                    |
| B — external registry (Docker Hub/private) | Registry-agnostic                                                         | Requires storing `REGISTRY_USERNAME`/`REGISTRY_PASSWORD`; secret handling/rotation | Heavier; unnecessary for the default |
| C — leave publish skipped (RFC-0009 only)  | No work                                                                   | Never publishes images                                                             | Doesn't satisfy #96                  |

The login step keeps `registry: ${{ vars.CONTAINER_REGISTRY }}`, so switching to an external
registry later only needs the variable + the two secrets back (documented inline).

## 4. Impact Assessment

| Area           | Impact        | Notes                                                                                 |
| -------------- | ------------- | ------------------------------------------------------------------------------------- |
| API / DB / PII | None          | CI/release tooling only                                                               |
| Security       | Positive      | No long-lived registry creds stored; keyless (OIDC) signing + SLSA provenance to GHCR |
| Supply chain   | Positive      | Released image is signed + SBOM-attested in GHCR (ADR-0029)                           |
| Release UX     | Positive      | Image publish works out of the box on GitHub-hosted repos                             |
| Permissions    | Uses existing | `packages: write` + `id-token: write` already on the workflow                         |

**Non-goal:** publishing to a non-GHCR registry by default, or changing the build itself.

## 5. Rollout Plan

1. Merge after DevOps + Security review (touches `.github/workflows/` → human review).
2. Next release (when `release_created == true`): `build-release-image` runs, pushes
   `ghcr.io/<owner>/repository-template-v2:<version>` + `:latest`, attaches SLSA provenance,
   cosign-signs (keyless), and attests the SBOM.
3. Smoke test: confirm the package appears under the repo's GHCR packages and the run is green
   (no `Username and password required`).

## 6. Rollback Plan

Revert this PR and/or unset the `CONTAINER_REGISTRY` variable. With the variable unset, the
RFC-0009 guard skips publish gracefully again. No data loss; published images/tags can be
deleted from GHCR if needed.

## 7. Timeline

| Milestone                | Target date        |
| ------------------------ | ------------------ |
| RFC approved             | 2026-06-07         |
| Implementation complete  | 2026-06-07         |
| Verified on next release | next release cycle |

## 8. Open Questions

- [ ] Apply the same GHCR-via-`GITHUB_TOKEN` pattern to `cd-staging.yml` (currently expects
      `REGISTRY_USERNAME`/`REGISTRY_PASSWORD`)? Follow-up if staging image push is desired.
- [ ] GHCR package visibility (private by default for private repos / public for public repos) —
      confirm the intended visibility after the first publish.

---

_Approved by:_ _(signatures go here after CAB review)_
