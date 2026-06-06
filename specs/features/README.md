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

## Spec Lifecycle

```
Draft → Under Review (PR open) → Approved (PR merged) → Implemented → Superseded
```

| Status           | Meaning                                                          |
| ---------------- | ---------------------------------------------------------------- |
| **Draft**        | Being authored; not yet submitted for review                     |
| **Under Review** | PR open; awaiting Tech Lead + Security Lead approval             |
| **Approved**     | PR merged to `main`; agents may implement                        |
| **Implemented**  | All acceptance criteria verified by tests in CI                  |
| **Superseded**   | Replaced by a newer spec version; old file kept for traceability |

---

## Creating a New Feature Spec

```bash
FEAT_ID=<github-issue-number>
mkdir -p specs/features/FEAT-${FEAT_ID}
cp .github/FEATURE_SPEC_TEMPLATE.md specs/features/FEAT-${FEAT_ID}/feature-spec.md
```

Then open a PR with the spec populated through sections 1–5 minimum before requesting review.

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
