# ADR-0083 — Frontend App Directory Rename

**Status:** Accepted
**Date:** 2026-06-15
**Authors:** Tech Lead, Frontend Lead
**Spec:** N/A — implementation-path refinement of an existing architectural decision
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0023](ADR-0023-frontend-architecture.md)

---

## Context

ADR-0023 established the frontend architecture and adopted a multi-app container layout —
`frontend/<app>/` — so the monorepo can host more than one frontend app over time. At scaffold
time the single shipped app was itself named `frontend`, producing the path `frontend/frontend/`.

This duplicated path (`frontend/frontend/`) is a recurring source of confusion: it reads like a
mistake, trips up newcomers navigating the tree, and forces awkward references throughout docs,
CI matrices, Dependabot config, and Makefile defaults. The duplication is purely an artefact of
the chosen app _name_, not of the container _pattern_ — the pattern itself (`frontend/<app>/`) is
sound and is the decision ADR-0023 made.

GitHub Issue #273 tracks flattening this confusion. ADR-0023 is an accepted ADR, and accepted
ADRs are append-only and immutable (AGENTS.md §5–§6); its architecture decision must not be
rewritten. A separate ADR is therefore the correct vehicle to record the directory rename.

## Decision

We will rename the single shipped frontend app directory from `frontend/frontend/` to
`frontend/web/`, and change the Makefile `APP` default from `frontend` to `web`.

This **refines the implementation path** of ADR-0023 without changing its architecture decision.
The multi-app container pattern `frontend/<app>/` is retained exactly as ADR-0023 specified — only
the app's name changes from `frontend` to `web`, eliminating the `frontend/frontend` duplication.
The outer `frontend/.env.example` (shared across apps in the container) stays in place.

The move is performed with `git mv` to preserve file history. All functional references that
resolve the path at build/CI time are updated in lockstep: the Makefile `APP` default, the
`ci-frontend.yml` build matrix, `.github/dependabot.yml` ecosystem directories, and `.gitignore`.
Live operational docs that cite the path are updated to remain accurate; historical records
(CHANGELOG, prior RFCs) keep their original `frontend/frontend` references as written.

## Consequences

### Positive

- Removes the confusing `frontend/frontend/` duplication; the app now lives at the self-describing
  `frontend/web/`.
- Preserves git history for every moved file via `git mv`.
- Keeps the ADR-0023 multi-app container pattern intact, so adding a second frontend app later
  (e.g. `frontend/admin/`) remains a drop-in operation.

### Negative / Trade-offs

- Open branches, forks, or local checkouts that reference `frontend/frontend/` must rebase onto
  the rename; stale paths will break until updated.
- The default Docker image tag derived from `${{ matrix.app }}` changes from `frontend` to `web`;
  consumers pinning the old image name must update.
- One more ADR to read alongside ADR-0023 to get the full picture of the frontend path.

### Neutral

- No change to framework, rendering, API-communication, auth, or test strategy — all of ADR-0023's
  substantive decisions are unchanged.

## Alternatives Considered

- **Flatten to a single `frontend/` (drop the container layer):** Rejected — it discards the
  multi-app pattern ADR-0023 deliberately chose and would block a future second frontend app
  without another restructure.
- **Leave `frontend/frontend/` as-is:** Rejected — the duplication is a persistent, low-value
  source of confusion (Issue #273); the one-time rename cost is small and preserves history.
- **Supersede ADR-0023 with a new architecture ADR:** Rejected — the architecture decision is not
  changing; only the implementation path is. A refining ADR is the proportionate, append-only
  (AGENTS.md §5–§6) way to record this.

## Compliance & Risk

- **Controls affected:** none — directory rename only; no boundary, auth, or data-flow change.
- **Data classification impact:** none.
- **Autonomy impact:** none — no HITL/HOTL or feature-flag behaviour changes.
- **Review/expiry:** permanent.

---

## Related

- `docs/adr/README.md` — master index & lifecycle definition
- `docs/adr/adr-review-checklist.md` — checklist to apply before marking this ADR `Accepted`
- [ADR-0023](ADR-0023-frontend-architecture.md) — the frontend architecture decision this refines
