# RFC-0006 — Migrate release-please to manifest mode (restore custom changelog sections)

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Release Manager, Tech Lead
> **Related Issue:** #93
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Related RFC:** RFC-0005 (version.txt sync) · **Related ADR:** ADR-0057, ADR-0028
> **Change type:** Normal

---

## 1. Context

`.github/workflows/release.yml` configures `google-github-actions/release-please-action@v4.1.1`
with an inline `changelog-types` input. **release-please v4 removed that input** — the action
emits `Unexpected input(s) 'changelog-types'` (observed in Release run `27100685645`, #93) and
**silently ignores** the repo's custom changelog taxonomy (Features / Bug Fixes / Security /
Privacy / Performance / Documentation; `chore` hidden). Release notes therefore fall back to
release-please defaults instead of the repo's conventional-commit sections.

The step runs under `continue-on-error: true`, so it is non-fatal — but the configured
sections are not honored.

## 2. Proposed Change

Adopt release-please **manifest mode** (the v4-idiomatic configuration):

1. **`release-please-config.json`** — declares the package at `.` with `release-type: python`
   and a `changelog-sections` array (the same taxonomy previously passed inline).
2. **`.release-please-manifest.json`** — seeded with the last released version (`2.10.2`), so
   release-please computes the next version from conventional commits.
3. **`release.yml`** — replace the inline `release-type` + `changelog-types` inputs with
   `config-file: release-please-config.json` + `manifest-file: .release-please-manifest.json`.

```yaml
with:
  config-file: release-please-config.json
  manifest-file: .release-please-manifest.json
```

### Interaction with RFC-0005

Manifest mode still bumps `pyproject.toml` (`release-type: python`). The RFC-0005 sync step
(mirror `pyproject.toml` → `version.txt`, the ADR-0057 SoT) is **unchanged and still required**:
`version.txt` is consumed raw and cannot carry release-please markers, so it is not added to
`extra-files` here. The two RFCs compose: RFC-0006 fixes changelog sections; RFC-0005 keeps the
SoT consistent.

## 3. Alternatives Considered

| Option                                                        | Pros                                                                                           | Cons                                               | Why rejected        |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------------- | ------------------- |
| A (proposed) — manifest mode                                  | v4-idiomatic; restores custom sections; declarative; future-proof (extra-files, multi-package) | Two new config files; one-time manifest seed       | —                   |
| B — drop `changelog-types`, accept defaults                   | Smallest diff                                                                                  | Loses the repo's section taxonomy in release notes | Defeats the purpose |
| C — pin action back to v3 (supports inline `changelog-types`) | No config files                                                                                | Stale major; loses v4 fixes/security; tech debt    | Backwards step      |

## 4. Impact Assessment

| Area            | Impact      | Notes                                                                                    |
| --------------- | ----------- | ---------------------------------------------------------------------------------------- |
| API / DB / PII  | None        | Release tooling only                                                                     |
| Security        | Neutral     | Same token/permissions                                                                   |
| Release notes   | Positive    | Custom sections honored again                                                            |
| Versioning      | Neutral     | Still `release-type: python`; manifest seeded at 2.10.2; RFC-0005 sync intact            |
| Existing PR #66 | Regenerated | release-please rebuilds its PR from the manifest; sections corrected on next `main` push |

**Non-goal:** changing the SoT (remains `version.txt`, ADR-0057) or the release cadence.

## 5. Rollout Plan

1. Merge this PR to `main` after DevOps/Release-Manager review (touches `.github/workflows/` → human review by design).
2. On the merge push, `release.yml` runs in manifest mode; release-please regenerates its PR
   (#66 or a successor) with the correct changelog sections, and the RFC-0005 step syncs `version.txt`.
3. Smoke test: confirm the Release run no longer logs the `changelog-types` warning and that the
   release PR's CHANGELOG uses the configured section headings.

## 6. Rollback Plan

Revert this PR and delete the two config files; the workflow returns to the prior inline config
(with the known v4 warning). No data or irreversible state. The manifest seed (2.10.2) matches
the current release, so reverting does not lose version history.

## 7. Timeline

| Milestone                               | Target date                     |
| --------------------------------------- | ------------------------------- |
| RFC approved                            | 2026-06-07                      |
| Implementation complete                 | 2026-06-07                      |
| Verified (no warning; sections correct) | next push to `main` after merge |

## 8. Open Questions

- [ ] Tag format: manifest mode with a single root component keeps `vX.Y.Z`; verify the next release tag matches the existing convention before cutting 2.11.0.
- [ ] Should `extra-files` later manage additional version-bearing files if any gain marker tolerance? (Out of scope; `version.txt` stays on the RFC-0005 sync.)

---

_Approved by:_ _(signatures go here after CAB review)_
