# RFC-0008 — Sync the README **Version:** badge on release-please PRs

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Release Manager
> **Related Issue:** #99
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Related RFC:** RFC-0005 (version.txt sync) · **Related ADR:** ADR-0057
> **Change type:** Normal

---

## 1. Context

`scripts/check_version_consistency.py` (a CI-enforced unit test, ADR-0057) validates **three**
representations of the framework version:

- `version.txt` (the single source of truth),
- `pyproject.toml` `version`,
- `README.md`'s `**Version:** X` badge.

(`CLAUDE.md`'s own `**Version:**` is the behavioral-contract version and is deliberately
excluded.)

release-please bumps `pyproject.toml`; RFC-0005 added a step that mirrors that into
`version.txt`. But **neither touches the README badge**. Cutting **2.11.0** therefore left
`README.md` at `2.10.2` while `version.txt`/`pyproject.toml` moved to `2.11.0`, and `main`
**failed** `tests/unit/process/test_version_consistency.py` (#99). PR #98 corrected the badge
by hand, but the gap recurs on every release.

## 2. Proposed Change

Extend the existing RFC-0005 sync step in `release.yml` to also update the README badge on the
release PR branch — mirroring `pyproject.toml`'s version into **both** `version.txt` and
`README.md`, committing if **either** changed:

```bash
README_VER="$(grep -m1 -oE '^> \*\*Version:\*\* [0-9]+\.[0-9]+\.[0-9]+' README.md \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
if [ -n "$README_VER" ] && [ "$README_VER" != "$VER" ]; then
  sed -i -E "s|^> \*\*Version:\*\* [0-9]+\.[0-9]+\.[0-9]+|> **Version:** ${VER}|" README.md
  changed=1
fi
```

Design notes:

- **No backreference** in the substitution — `\1${VER}` would misparse as a multi-digit
  backref (`\12.12.0` → group 12). The replacement re-writes the literal prefix instead, which
  is correct for any version (verified for `2.12.0` and `10.0.0`).
- The step now commits when **version.txt OR README** changed (previously it early-exited once
  `version.txt` was consistent, which would have skipped README).
- Only `README.md` is edited; `CLAUDE.md`'s contract version is never touched (matching the
  consistency checker's exclusion).
- Same reliability properties as RFC-0005: runs after the action every push to `main`
  (survives force-push), no workflow loop, `continue-on-error`, no-op when consistent.

## 3. Alternatives Considered

| Option                                               | Pros                                                        | Cons                                                                                         | Why rejected                                 |
| ---------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------- |
| A (proposed) — extend the RFC-0005 sync to README    | One mechanism for all version files; reliable; minimal diff | Bot edits README on the release PR                                                           | —                                            |
| B — drop the README badge from the consistency check | No release-time work                                        | Loses a useful drift guard; weakens ADR-0057 enforcement                                     | Reduces guarantees                           |
| C — add release-please `extra-files` for README      | Declarative                                                 | README badge line can't carry release-please markers without altering rendered docs; brittle | Same constraint as version.txt (RFC-0005 §1) |
| D — bump README by hand each release                 | No automation                                               | Error-prone; exactly the recurring failure #99 documents                                     | Defeats the purpose                          |

## 4. Impact Assessment

| Area            | Impact                  | Notes                                                               |
| --------------- | ----------------------- | ------------------------------------------------------------------- |
| API / DB / PII  | None                    | Release tooling only                                                |
| Security        | Neutral                 | Same token/permissions as RFC-0005                                  |
| Release process | Positive                | README badge stays consistent; `main` no longer breaks post-release |
| Scope           | 1 step in `release.yml` | Builds on RFC-0005                                                  |

**Non-goal:** changing the SoT (`version.txt`, ADR-0057) or the consistency checker.

## 5. Rollout Plan

1. Merge after DevOps/Release-Manager review (touches `.github/workflows/` → human review).
2. On the next release PR, confirm the sync commit updates **both** `version.txt` and the README
   badge, and that `test_version_consistency` stays green after the release lands on `main`.
3. Smoke test: a release run logs `README **Version:** … -> <new>` (or "already consistent").

## 6. Rollback Plan

Revert this PR — the step reverts to syncing `version.txt` only (RFC-0005 behaviour); README
would again need a manual bump per release. No data or irreversible state.

## 7. Timeline

| Milestone                   | Target date        |
| --------------------------- | ------------------ |
| RFC approved                | 2026-06-07         |
| Implementation complete     | 2026-06-07         |
| Verified on next release PR | next release cycle |

## 8. Open Questions

- [ ] Should the consistency checker and this sync be generalized to a single declared list of
      "version-bearing files" so future additions are covered automatically? (Refactor; separate.)

---

_Approved by:_ _(signatures go here after CAB review)_
