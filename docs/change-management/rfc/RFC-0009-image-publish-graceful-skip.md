# RFC-0009 — Skip image publish gracefully when no registry is configured

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Release Manager
> **Related Issue:** #96
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Change type:** Normal

---

## 1. Context

Cutting release **2.11.0** created the GitHub Release + tag successfully, but the
`build-release-image` job in `release.yml` **failed** with `Username and password required`
(`docker/login-action` got empty creds). The repo has no container-registry config:
`vars.CONTAINER_REGISTRY`, `secrets.REGISTRY_USERNAME`, `secrets.REGISTRY_PASSWORD` are unset
(#96).

For a **template** repo (or any fork that doesn't publish images), this is the normal state —
yet every release shows a **red job**, which is misleading: the release itself succeeded; only
the optional image publish couldn't run. We want the absence of a registry to be a _graceful
skip with an explanation_, not a failure. (Actually configuring the registry remains tracked in
#96 — this RFC removes the false-failure symptom, it does not publish images.)

## 2. Proposed Change

In `.github/workflows/release.yml`:

1. **Guard `build-release-image`** so it runs only when a release was created **and** a registry
   is configured:

   ```yaml
   if: needs.release-please.outputs.release_created == 'true' && vars.CONTAINER_REGISTRY != ''
   ```

   When `CONTAINER_REGISTRY` is unset, the job is **skipped** (neutral), not failed.

2. **Add a small `image-publish-skipped` job** that runs only when a release was created and the
   registry is **not** configured, emitting a `::notice::` that explains the skip and how to
   enable publishing:
   ```yaml
   image-publish-skipped:
     needs: release-please
     if: needs.release-please.outputs.release_created == 'true' && vars.CONTAINER_REGISTRY == ''
     steps:
       - run: echo "::notice title=Image publish skipped::… set CONTAINER_REGISTRY + REGISTRY_USERNAME/REGISTRY_PASSWORD … (issue #96)"
   ```

Exactly one of the two jobs runs per release; both skip when no release is created.

## 3. Alternatives Considered

| Option                                           | Pros                                                   | Cons                                                                                                   | Why rejected         |
| ------------------------------------------------ | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | -------------------- |
| A (proposed) — guard + notice job                | No false failures; clear guidance; release stays green | One extra tiny job                                                                                     | —                    |
| B — `continue-on-error: true` on the publish job | One line                                               | Hides _real_ publish failures too (when a registry IS configured); no guidance                         | Masks genuine errors |
| C — require registry config (fail by design)     | Forces setup                                           | Breaks every template/fork release until creds exist; poor day-zero UX (ADR-0059 progressive adoption) | Hostile default      |
| D — delete the publish job                       | Simplest                                               | Loses image publish for repos that DO configure a registry                                             | Removes capability   |

## 4. Impact Assessment

| Area                  | Impact           | Notes                                                                 |
| --------------------- | ---------------- | --------------------------------------------------------------------- |
| API / DB / PII        | None             | CI/release tooling only                                               |
| Security              | Neutral→positive | Still signs/attests when a registry IS configured; no creds bypass    |
| Release UX            | Positive         | No false-red job on registry-less releases; actionable notice         |
| Repos WITH a registry | None             | `build-release-image` runs unchanged when `CONTAINER_REGISTRY` is set |

**Non-goal:** configuring an actual registry (still tracked in #96) or changing the build/sign/SBOM
steps themselves. This RFC scopes to `release.yml`; `cd-staging.yml` could get analogous treatment
as a follow-up if its registry-less runs prove noisy.

## 5. Rollout Plan

1. Merge after DevOps review (touches `.github/workflows/` → human review).
2. Next release with no registry configured → `build-release-image` shows **skipped**, and
   `image-publish-skipped` shows **success** with the explanatory notice; the GitHub Release is green.
3. If/when #96 configures a registry → `build-release-image` runs and publishes as before;
   `image-publish-skipped` is skipped.

## 6. Rollback Plan

Revert this PR — restores the prior unconditional `build-release-image` job (which fails without
a registry). No data or irreversible state.

## 7. Timeline

| Milestone                | Target date        |
| ------------------------ | ------------------ |
| RFC approved             | 2026-06-07         |
| Implementation complete  | 2026-06-07         |
| Verified on next release | next release cycle |

## 8. Open Questions

- [ ] Apply the same guard to `cd-staging.yml` (and any other registry-dependent job) so
      registry-less deploys also skip gracefully? (Follow-up if needed.)

---

_Approved by:_ _(signatures go here after CAB review)_
