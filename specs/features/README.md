# Feature Specs

> **Owner:** Tech Lead | **Phase:** 4 (Specification)
> **ADR:** ADR-0052 | **Workflow:** `docs/process/WORKFLOW.md §Phase 4`

This directory contains the machine-readable, human-approved feature specifications that bound agent implementation. No code may be written for a feature without an approved spec in this directory (SDD invariant — CLAUDE.md §2, §3.4).

---

## Directory Structure

```
specs/features/
└── FEAT-{id}/
    └── feature-spec.md   ← Full feature spec (from .github/FEATURE_SPEC_TEMPLATE.md)
```

`{id}` matches the GitHub Issue number for the parent feature request.

---

## Spec Lifecycle (ADR-0085)

```
draft → in-review (PR open) → approved (PR merged) → implemented → superseded
```

Same five lower-case values as every other spec (`specs/README.md`), in the frontmatter
`status:` field. A feature spec's `id` is `SPEC-FEAT-<NNN>` (or its domain's code); the
`FEAT-{issue}` directory name is the GitHub-issue alias recorded as `issue:`.

---

## Creating a New Feature Spec

```bash
FEAT_ID=<github-issue-number>
mkdir -p specs/features/FEAT-${FEAT_ID}
cp .github/FEATURE_SPEC_TEMPLATE.md specs/features/FEAT-${FEAT_ID}/feature-spec.md
```

Fill the frontmatter (`id`, `kind: feature-spec`, `status: draft`, `issue`) and sections 1–5 minimum, then open a PR for review. The template is a *profile* of `specs/SPEC-TEMPLATE.md` (W13-T8): it carries the same FR→AC coverage footer, Open Questions and Assumptions sections.

---

## Spec Review Requirements

| Reviewer      | Required when                                                                            |
| ------------- | ---------------------------------------------------------------------------------------- |
| Tech Lead     | Always                                                                                   |
| Security Lead | Feature introduces new PII processing, new attack surface, or modifies `src/guardrails/` |
| Product Owner | Acceptance criteria alignment check (sections 1–2)                                       |

The CI `harness/governance.yml` spec lint gate validates automatically:

- Spec file exists for `feat`/`fix`/`security` PRs referencing a FEAT-ID
- All ADR references in the spec exist in `docs/adr/`
- `allowed_action_types` section present if spec touches `src/agents/`

---

## Naming Conventions

| Pattern         | Example                                                          |
| --------------- | ---------------------------------------------------------------- |
| Directory       | `FEAT-42/` — matches Issue #42                                   |
| Spec file       | `feature-spec.md` (always this name)                             |
| Superseded spec | `feature-spec-v1.md` (rename old; new becomes `feature-spec.md`) |

---

## Related

- Template: `.github/FEATURE_SPEC_TEMPLATE.md`
- Discovery artefacts: `docs/product/FEAT-{id}/`
- ADR template: `docs/adr/README.md`
- Spec lifecycle skill: `skills/sdlc/spec-lifecycle.md`
- Workflow: `docs/process/WORKFLOW.md`
