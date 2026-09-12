# ADR-0087 — Marker-Based Three-Way Template Sync

**Status:** Accepted
**Date:** 2026-09-12
**Authors:** DevOps Lead · Tech Lead (drafted with Claude Code, Wave 14 · W14-T1, issue #376)
**Spec:** N/A — operational policy (adopter tooling)
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0059](ADR-0059-reusability-uplift.md) (partially amended: the sync mechanism), [ADR-0084](ADR-0084-dependency-updates-via-dependabot.md)

---

## Context

ADR-0059's `template-sync.yml` brought template updates to adopters by
`git checkout template/main -- .` and then restoring a hard-coded list of nine paths. Every
adopter edit outside that list — a customised `Makefile`, `pyproject.toml`, `ci.yml`, a service
Dockerfile — was overwritten in the weekly draft PR. The template URL and the exclude list lived
inside the workflow, so an adopter could change neither without editing a synced file, and
nothing recorded which template commit an adopter was on, so "what changed since my last sync"
was unanswerable.

## Decision

We will sync by **three-way merge against a recorded base**:

1. `.template-version` in the adopter repo records the template commit (and timestamp) of the
   last sync. `make template-init` writes it; each sync updates it.
2. `scripts/template_sync.sh` computes `git diff --name-status <recorded-base> <template-tip>`
   and, per path: fast-forwards files the adopter never touched, `git merge-file`s files both
   sides changed (leaving conflict markers only where hunks overlap), adds new template files,
   removes files the template deleted and the adopter never modified, and never touches paths
   listed in the adopter-owned `.template-sync.yml` (`exclude:`).
3. `template-sync.yml` calls that script and opens the draft PR as before; the template URL comes
   from the `TEMPLATE_REPO_URL` repository variable (fallback: this repository).
4. The previous whole-tree workflow is kept for one release as `template-sync-legacy.yml`
   (`workflow_dispatch` only) and then removed.
5. `tests/unit/governance/test_template_sync.py` builds a fixture template and adopter in
   temporary git repositories and proves: an adopter-modified `Makefile` survives a sync, a file
   only the template changed fast-forwards, an overlapping change produces conflict markers, and
   an excluded path is never written.

## Consequences

### Positive

- Adopters keep their edits; the sync PR contains only template deltas and explicit conflicts.
- The base is explicit, so the sync PR body can list the template commits being applied.
- The exclude list is data the adopter owns.

### Negative / Trade-offs

- Conflict markers can land in the draft PR; the reviewer must resolve them (the previous
  behaviour silently discarded the adopter's side, which was worse but looked cleaner).
- Renames are handled as delete + add; a renamed-and-modified file may need manual attention.

## Alternatives Considered

- **copier / cruft.** Rejected for now: both require re-templating the repository with
  answer files; the marker-based merge gives the same three-way property with git alone and no
  new tool for adopters.
- **git subtree / merge with unrelated histories.** Rejected: ADR-0059 already replaced it as
  too fragile for adopters that squash-merge.

## Compliance & Risk

- **Controls affected:** none. **Data classification impact:** none. **Autonomy impact:** none.
- **Review/expiry:** revisit when the legacy workflow is removed (one release).

---

## Related

- Seven-Axis Review §4 Portability (2026-09-12) · Template v2 Improvement Plan W14-T1
