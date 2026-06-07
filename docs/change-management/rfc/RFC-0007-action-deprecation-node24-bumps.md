# RFC-0007 — Resolve release-please rename + Node 20 action deprecations

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Release Manager
> **Related Issue:** #97
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Related RFC:** RFC-0005 (version.txt sync), RFC-0006 (manifest mode)
> **Change type:** Normal

---

## 1. Context

The Release workflow (run `27101307155`) logged deprecation warnings:

1. **Action moved:** `google-github-actions/release-please-action is deprecated, please use
googleapis/release-please-action instead.`
2. **Node 20 sunset:** the pinned release-please action (and `docker/login-action`) run on
   Node.js 20 — GitHub forces Node 24 from **2026-06-16** and removes Node 20 on
   **2026-09-16**.

Non-fatal today, but the actions will break / be force-migrated around those dates. The pins
affected:

- `google-github-actions/release-please-action@…e4dc86ba… # v4.1.1` (`release.yml`)
- `docker/login-action@…c94ce9fb… # v3.7.0` (`release.yml`, `cd-staging.yml`, `sbom.yml`)

## 2. Proposed Change

Bump both actions to current, **Node-24** releases, SHA-pinned (repo convention):

| Action            | Old                                                                       | New                                                                                           |
| ----------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| release-please    | `google-github-actions/release-please-action@e4dc86ba… # v4.1.1` (node20) | `googleapis/release-please-action@45996ed1f6d02564a971a2fa1b5860e934307cf7 # v5.0.0` (node24) |
| docker login (×3) | `docker/login-action@c94ce9fb… # v3.7.0` (node20)                         | `docker/login-action@650006c6eb7dba73a995cc03b0b2d7f5ca915bee # v4.2.0` (node24)              |

Verified before adoption (via the actions' `action.yml` at the pinned SHAs): both declare
`using: 'node24'`, and `release-please-action` v5 supports the `config-file` + `manifest-file`
inputs — i.e. it is compatible with the manifest-mode configuration introduced in RFC-0006.

### Why v5 is safe here

release-please v5 is **manifest-mode-centric** (it dropped the legacy inline single-input
mode). RFC-0006 already moved this repo to manifest mode (`release-please-config.json` +
`.release-please-manifest.json`), so the v4→v5 major bump requires **no further config
change**. The RFC-0005 `version.txt` sync step is independent and unchanged.

## 3. Alternatives Considered

| Option                                                       | Pros                                                         | Cons                                                                                 | Why rejected              |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------------------------------ | ------------------------- |
| A (proposed) — bump to googleapis v5 + login v4.2.0          | Removes deprecation + Node-20 risk; future-proof; SHA-pinned | Major bump (v4→v5)                                                                   | —                         |
| B — stay on v4.1.1, set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` | Minimal diff                                                 | Still on the _deprecated repo_; an env hack, not a fix; breaks after Node 20 removal | Temporary, not a real fix |
| C — do nothing until 2026-06-16                              | No work now                                                  | Forced auto-migration on a deprecated action is risky and unowned                    | Avoidable tech debt       |

## 4. Impact Assessment

| Area              | Impact                    | Notes                                                                                                       |
| ----------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------- |
| API / DB / PII    | None                      | CI/release tooling only                                                                                     |
| Security          | Positive                  | Maintained, Node-24 actions; SHA-pinned                                                                     |
| Release behaviour | Neutral                   | v5 keeps manifest config + outputs (`release_created`, `tag_name`, `version`) used by `build-release-image` |
| Scope             | 4 pins across 3 workflows | release-please (1) + docker/login-action (3)                                                                |

**Out of scope:** a full repo-wide audit of _every_ Node-20-pinned action. This RFC fixes the
two actions whose deprecations actually fired in #97; a broader sweep can follow if desired.

## 5. Rollout Plan

1. Merge after DevOps review (touches `.github/workflows/` → human review by design).
2. Next push to `main` runs `release.yml` on v5; confirm **no** `changelog-types`/deprecated-repo/Node-20 warnings for these actions, and that the release PR + version.txt sync still function (RFC-0005/0006 intact).
3. `cd-staging.yml` / `sbom.yml` use the new `docker/login-action` on their next trigger.

## 6. Rollback Plan

Revert this PR — restores the prior pins (with the known deprecation warnings). No data or
irreversible state. Outputs consumed downstream are unchanged, so dependent jobs are unaffected
by a rollback.

## 7. Timeline

| Milestone               | Target date                                                             |
| ----------------------- | ----------------------------------------------------------------------- |
| RFC approved            | 2026-06-07                                                              |
| Implementation complete | 2026-06-07                                                              |
| Verified warning-free   | next push to `main` after merge (before the 2026-06-16 Node-24 cutover) |

## 8. Open Questions

- [ ] Should a recurring "action freshness" check (e.g. Dependabot for GitHub Actions, or a scheduled audit) be added so Node-runtime deprecations are caught proactively rather than at release time? (Separate proposal.)

---

_Approved by:_ _(signatures go here after CAB review)_
