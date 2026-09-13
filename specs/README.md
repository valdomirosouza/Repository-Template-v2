# Specs — Spec-Driven Development

All implementation in this repository is governed by a spec. No PR may be merged
without referencing a spec path from this directory.

**Rule:** Write the spec → get it approved → then write the code.

---

## Spec Lifecycle (ADR-0085)

```
draft → in-review → approved → implemented → superseded
```

| Status          | Meaning                                                                          |
| --------------- | -------------------------------------------------------------------------------- |
| **draft**       | Being written; not yet reviewable                                                |
| **in-review**   | Spec PR open; under review by owner and reviewer                                 |
| **approved**    | Binding; implementation must follow this spec (code may start)                   |
| **implemented** | Code matches spec; spec is the record of what was built                          |
| **superseded**  | Replaced by a newer spec (`superseded_by:`); file moved to `specs/deprecated/`  |

Exactly these five lower-case values, in the YAML frontmatter `status:` field. Gates treat only
`approved` and `implemented` as binding (`check_open_questions.py`, the PR spec-reference gate,
`build_spec_registry.py`).

---

## Identity & Naming (ADR-0085)

Every spec carries frontmatter (`specs/spec-frontmatter.schema.json`):

```yaml
---
id: SPEC-API-005          # SPEC-<DOMAIN>-<NNN> — the only spec identifier
kind: spec                # spec | feature-spec | threat-model (companions share the parent id)
status: approved
owner: Tech Lead
issue: 412                # GitHub issue that delivers/owns it (null until assigned)
governing_adrs: [ADR-0003]
implemented_by: [src/api/rest/routers/requests.py]
verified_by: [tests/unit/api/test_requests.py]
related_specs: []
last_updated: 2026-09-12
---
```

New specs are named `specs/<domain>/SPEC-<DOMAIN>-<NNN>-<slug>.md`. Existing path-named specs
keep their filenames; their id lives in the frontmatter (backfilled by
`scripts/governance/migrate_spec_frontmatter.py`, W13-T2). Feature work lives under
`specs/features/FEAT-{issue}/` — the directory is the issue alias, the id is still `SPEC-…`.

Examples:

- `specs/ai/agent-design.md` (`id: SPEC-AI-001`)
- `specs/api/SPEC-API-002-idempotency-keys.md`
- `specs/features/FEAT-001/feature-spec.md` (`id: SPEC-FEAT-001`, `issue: 357`)

---

## Registry (generated)

`docs/governance/spec-registry.md` is **generated** by `make spec-registry`
(`scripts/governance/build_spec_registry.py`) from the frontmatter, the `Spec:` docstring
references in `src/` and `tests/`, the `@pytest.mark.requirement(...)` markers and
`services.yaml` `spec:` fields. It replaces the hand-maintained ownership table that used to live
here (11 rows, all "Approved", none verified). CI fails when the registry is stale or a rule
S1–S7 is violated.

---

## How to Reference a Spec in a PR

In the PR description (`.github/pull_request_template.md`):

```
## Referenced Spec
specs/ai/guardrails.md
```

In a commit message:

```
feat(guardrails): add CPF detection pattern

Refs: #42, SPEC-AI-007, ADR-0012
```

---

## How to Update a Spec

- **Minor clarifications** (no behaviour change): PR by spec owner; single reviewer
- **Major changes** (behaviour or interface change): new ADR required; spec version incremented; PR reviewed by owner + all implementers

When implementation diverges from the spec, the spec must be updated in the same PR
that makes the implementation change — they must stay in sync.
