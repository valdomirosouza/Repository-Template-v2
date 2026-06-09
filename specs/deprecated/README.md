# `specs/deprecated/` — archive of retired specs

Specs are **decision records**. When a spec is superseded or retired we **move it here — we do
not delete it** — so the history of what we decided, and why, is preserved.

## Convention (see `skills/sdlc/spec-lifecycle.md`)

- A spec reaching `status: superseded` is relocated with
  `git mv specs/<domain>/<file>.md specs/deprecated/<file>.md` — **never `git rm`**.
- The moved file keeps `status: superseded` and records its replacement (`superseded_by:` /
  `related_specs`). Its `id` is never re-used.
- `specs/README.md` is updated to reflect the move.
- Moving a spec here is a **governance action** — it goes through Spec-as-PR review (specs are not
  auto-merged; CLAUDE.md §2, auto-merge review-gate).

Files in this folder are archived: excluded from "active spec" tooling, retained in history.
