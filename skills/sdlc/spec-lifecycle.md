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

| Transition             | Who approves              | What changes                          |
| ---------------------- | ------------------------- | ------------------------------------- |
| Draft → Review         | Spec author               | Open PR; tag spec owner and reviewer  |
| Review → Approved      | Owner + Reviewer          | Merge PR; update status field in spec |
| Approved → Implemented | Tech Lead                 | After implementation PR merges        |
| Approved → Deprecated  | Tech Lead + Product Owner | Link to superseding spec              |

---

## Writing a New Spec

1. Create file at `specs/<domain>/<name>.md`
2. Add header block:

   ```markdown
   # <Title>

   **Status:** Draft | **Owner:** <Role> | **Last updated:** YYYY-MM-DD
   **ADR references:** ADR-NNNN (if applicable)
   ```

3. Add to the ownership table in `specs/README.md`
4. Open a PR for review — do not start implementation until status is `Approved`

**Naming convention:** `specs/<domain>/<kebab-case-name>.md`

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

## Checklist: Is This Spec Ready to Implement?

- [ ] Status is `Approved` (not Draft or Review)
- [ ] Owner and Reviewer have signed off in the PR comments
- [ ] All terms are defined in `docs/glossary.md`
- [ ] Success metrics are measurable (not vague)
- [ ] Privacy impact assessed (DPIA/RIPD required if new PII processing)
- [ ] Referenced ADRs exist and are `Accepted`
