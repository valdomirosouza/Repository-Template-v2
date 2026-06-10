# Skill — Spec Lifecycle (SDD)

**Owner:** Tech Lead | **Reviewer:** Product Owner | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill when writing, reviewing, or updating a spec.

---

## The SDD Rule

**No code without a spec.** If asked to implement something without a spec, write the spec
first and get it approved. This is enforced by the PR template (spec path is required)
and CLAUDE.md step 1.

---

## Spec Lifecycle

```
Draft → Review → Approved → Implemented → Deprecated
```

| Transition             | Who approves              | What changes                                                                                                  |
| ---------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Draft → Review         | Spec author               | Open PR; tag spec owner and reviewer                                                                          |
| Review → Approved      | Owner + Reviewer          | Merge PR; update status field in spec                                                                         |
| Approved → Implemented | Tech Lead                 | After implementation PR merges                                                                                |
| Approved → Deprecated  | Tech Lead + Product Owner | Set `status: superseded`, link the superseding spec, and **move the file to `specs/deprecated/`** (see below) |

### Deprecating a spec — move, never delete

Specs are **decision records**: a superseded spec is still evidence of _what we decided and why_,
so it is **preserved, not removed**.

- When a spec reaches `status: superseded` (or is otherwise retired), **move** it with
  `git mv specs/<domain>/<file>.md specs/deprecated/<file>.md` — **never `git rm`** it.
- In the moved file's metadata, keep `status: superseded` and add the superseding spec to
  `related_specs` (e.g. `superseded_by: SPEC-XXX-NNN`).
- Update the ownership table in `specs/README.md` to reflect the move.
- The `id` stays unique forever — never re-issue a retired spec's id.

`specs/deprecated/` is an archive; its contents are excluded from "active spec" tooling but kept in
history. Moving a spec there is a governance action (Spec-as-PR review applies — it is not
auto-merged).

---

## Writing a New Spec

1. **Copy the canonical template:** [`specs/SPEC-TEMPLATE.md`](../../specs/SPEC-TEMPLATE.md) →
   `specs/<domain>/SPEC-<DOMAIN>-<NNN>-<slug>.md`. Its machine-readable metadata header and 16
   sections map 1:1 onto the 15-phase workflow (ADR-0058) and carry a _section → phase_ map, so
   the spec is directly drivable by `/deliver`. Keep every heading; write `N/A — <reason>` where
   a section truly does not apply.
2. Fill every section. Pay special attention to **§5 Functional Requirements** (each must trace
   to an acceptance criterion) and **§12 Acceptance Criteria** (observable & runnable — these
   become the dry-run evidence in `/deliver`'s FINAL-REPORT).
3. Add to the ownership table in `specs/README.md`.
4. Open a PR for review — do not start implementation until `status: approved`.
5. _(Optional)_ Dry-run the full lifecycle: `/deliver specs/<domain>/<your-spec>.md` →
   `reports/<slug>/FINAL-REPORT.md` (governed, no side-effects).

**Naming convention:** `specs/<domain>/<kebab-case-name>.md` (template uses `SPEC-<DOMAIN>-<NNN>-<slug>`).

---

## Updating an Existing Spec

- **Minor clarification** (no behaviour change): PR by spec owner, single reviewer, no ADR needed.
- **Major change** (new behaviour, interface change, security implication):
  1. File a new ADR documenting the architectural decision
  2. Increment a version comment in the spec header
  3. PR reviewed by owner + all teams implementing the spec

When implementation diverges from the spec, **update the spec in the same PR** — they must
stay in sync. A diverging implementation without a spec update is a compliance violation.

---

## Spec → Code → Test Traceability

Every implementation file must reference its governing spec in the module docstring:

```python
"""Short description of what this module does.

Spec: specs/ai/guardrails.md (Layer 1 — PII Filter)
ADR:  ADR-0012 (PII Masking Strategy)
"""
```

Every PR must reference a spec in the PR template field:

```
## Referenced Spec
specs/ai/guardrails.md
```

---

## `SPEC_DEVIATION` markers — record when code diverges from the spec

When implementation must diverge from the spec or design (an unavoidable trade-off, a discovered
constraint), make the drift **greppable and gateable** instead of silent. Coverage and lint cannot
see "the code quietly stopped matching the spec"; an inline marker turns it into an auditable fact
that complements requirement-ID traceability.

Place the marker at the point of divergence, always paired with a reason:

```python
# SPEC_DEVIATION: store retries in Redis, not Postgres as specs/foo.md §9 states
# Reason: Postgres write amplification breached the §10 latency budget; see ADR-00NN / #123
```

Rules:

1. **Always paired.** A `# SPEC_DEVIATION: <what>` line must be followed by a `# Reason: <why>`.
2. **Always mapped.** Every open deviation must map to a tracked decision — an ADR, an issue, or a
   spec update — before merge (enforced via the `CLAUDE.md §7` PR checklist). An unmapped
   deviation blocks merge: either land the ADR/issue or fix the code to match the spec.
3. **Surfaced in CI.** `harness/code-check.yml` (`spec-deviation-markers`) greps the diff and lists
   every added `SPEC_DEVIATION` in the PR summary so reviewers see the drift explicitly.
4. **Temporary by default.** A deviation is debt: resolve it (update the spec, or revert the code)
   rather than letting markers accumulate. The sub-agent return envelope reports open markers
   (`docs/sdlc/agent-handoff-schema.md`).

The marker works in any language — use that language's line-comment syntax (`//`, `#`, `--`).

---

## Checklist: Is This Spec Ready to Implement?

- [ ] Status is `Approved` (not Draft or Review)
- [ ] Owner and Reviewer have signed off in the PR comments
- [ ] All terms are defined in `docs/glossary.md`
- [ ] Success metrics are measurable (not vague)
- [ ] Privacy impact assessed (DPIA/RIPD required if new PII processing)
- [ ] Referenced ADRs exist and are `Accepted`
