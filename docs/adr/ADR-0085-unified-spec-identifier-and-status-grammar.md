# ADR-0085 — Unified Spec Identifier and Status Grammar

**Status:** Accepted
**Date:** 2026-09-12
**Authors:** Tech Lead · Product Owner (drafted with Claude Code, Wave 13 · W13-T1, issue #366)
**Spec:** specs/SPEC-TEMPLATE.md (metadata header) · specs/sdlc/development-lifecycle.md
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0058](ADR-0058-agentic-spec-driven-delivery-workflow.md), [ADR-0064](ADR-0064-delivery-right-sizing-tiers.md), [ADR-0065](ADR-0065-test-integrity-invariants.md), [ADR-0089](ADR-0089-documented-capability-reachability-invariant.md)

---

## Context

The Seven-Axis Review (2026-09-12) found four identifier grammars in simultaneous use:

| Grammar                                 | Where defined                                                       | Live instances                       |
| --------------------------------------- | ------------------------------------------------------------------- | ------------------------------------ |
| `SPEC-<DOMAIN>-NNN`                     | `specs/SPEC-TEMPLATE.md` frontmatter `id:`                          | 7 numbered specs                     |
| path-as-id (`specs/<domain>/<name>.md`) | `specs/README.md` naming convention                                 | ~49 specs, no frontmatter            |
| `FEAT-{issue}`                          | `specs/features/README.md` and the 15-phase delivery agents         | directory convention, zero instances |
| `SPEC-NNN`                              | CLAUDE.md §6 (branch/commit grammar) and §7.1 (spec-reference gate) | zero specs match                     |

and three status vocabularies (`Draft → Review → Approved → Implemented → Deprecated` in
`specs/README.md`; `draft | in-review | approved | implemented | superseded` in the template;
`Draft → Under Review → Approved → Implemented → Superseded` in `specs/features/README.md`).
49 of 57 specs carry no machine-readable `status:` at all, so the onboarding rule "confirm the
spec is Approved before any file write" cannot be checked, and the PR spec-reference gate can
only string-match a path. Traceability from requirement to delivery breaks at its first hop.

## Decision

We will use **one identifier grammar and one status vocabulary**, carried as YAML frontmatter
on every spec and validated in CI:

1. **Identifier.** `SPEC-<DOMAIN>-<NNN>` is the only spec id. `<DOMAIN>` is an upper-case code
   for the `specs/<domain>/` directory (`AI`, `API`, `SYS`, `PRIV`, `SEC`, `OBS`, `SRE`, `COMP`,
   `ETH`, `GOV`, `K8S`, `SDLC`, `INFRA`, `LGS`, `AUTO`); `<NNN>` is zero-padded and unique
   within the domain. Existing path-named files keep their filenames — the id lives in the
   frontmatter — and **new** specs are named `SPEC-<DOMAIN>-<NNN>-<slug>.md`.
2. **Feature specs are not a namespace.** `FEAT-{issue}` becomes the directory name under
   `specs/features/` and the frontmatter carries `issue: <n>`; the spec's `id` is still a
   `SPEC-<DOMAIN>-<NNN>` (domain `FEAT` for cross-cutting features, else the feature's domain).
   Companion documents (threat model, feature-spec profile) share the parent id and declare
   `kind: threat-model | feature-spec`.
3. **Status.** `draft | in-review | approved | implemented | superseded` — lower-case, exactly
   these five. `Deprecated` and `Under Review` are retired spellings. Gates that read status
   (`check_open_questions.py`, the spec-reference PR gate, the registry builder) treat only
   `approved` and `implemented` as binding.
4. **Frontmatter schema** (`specs/spec-frontmatter.schema.json`, validated by
   `scripts/governance/build_spec_registry.py`):
   `id`, `kind`, `status`, `owner`, `issue`, `governing_adrs[]`, `implemented_by[]`,
   `verified_by[]`, `related_specs[]`, `last_updated`, plus the template's existing
   `source`, `new_adrs_required`, `slo_ref`. `implemented_by` / `verified_by` are the code and
   test paths that realise the spec — the registry checks they exist.
5. **Branch and commit grammar** (CLAUDE.md §6) uses the real id:
   `feature/SPEC-API-005-<desc>` and `Refs: #<issue>, SPEC-API-005, ADR-NNNN`. The `REM-NNN`
   form remains valid for remediation items.
6. **Migration** (W13-T2) backfills frontmatter mechanically: the id is allocated per domain,
   the status is carried from the spec's own `**Status:**` body line when present
   (`Approved`/`Accepted` → `approved`, anything else → `draft`) and recorded with a
   `status_source`, and never promoted beyond what the document already claimed.

## Consequences

### Positive

- Every hop of the traceability chain has a machine-readable anchor: spec id → file → status →
  issue → ADRs → code → tests. The registry (W13-T3) is generated, not maintained.
- "Spec must be approved before code" is checkable by a script and by the PR gate.
- Agents stop mixing `SPEC-{feat-id}` and `FEAT-{id}`; one grammar in prompts and docs.

### Negative / Trade-offs

- A one-time mechanical change to ~50 files; reviewers should check the carried-over statuses,
  not the diff noise.
- Two spellings retired; any external link to "Under Review" wording is stale.

### Neutral

- The path convention `specs/<domain>/<name>.md` remains valid for reading; only new files use
  the id-prefixed filename.

## Alternatives Considered

- **Keep path-as-id.** Rejected: paths are not stable identifiers (moves under
  `specs/deprecated/` break every reference) and cannot carry status.
- **Make `FEAT-{issue}` the primary id.** Rejected: an issue number is a delivery artefact,
  not a requirement identity; a spec can be re-delivered under a new issue.
- **A central index file maintained by hand.** Rejected: that is the `specs/README.md`
  ownership table, which was already wrong (11 rows, all "Approved", none machine-checked).

## Compliance & Risk

- **Controls affected:** none directly; strengthens SDD invariant (CLAUDE.md §3.4).
- **Data classification impact:** none.
- **Autonomy impact:** none.
- **Review/expiry:** permanent.

---

## Related

- Seven-Axis Review §1 Ambiguity handling and §6 Traceability (2026-09-12)
- Template v2 Improvement Plan, Wave 13
