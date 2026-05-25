# Specs — Spec-Driven Development

All implementation in this repository is governed by a spec. No PR may be merged
without referencing a spec path from this directory.

**Rule:** Write the spec → get it approved → then write the code.

---

## Spec Lifecycle

```
Draft → Review → Approved → Implemented → Deprecated
```

| Status          | Meaning                                                 |
| --------------- | ------------------------------------------------------- |
| **Draft**       | Being written; not yet reviewable                       |
| **Review**      | Under review by owner and reviewer                      |
| **Approved**    | Binding; implementation must follow this spec           |
| **Implemented** | Code matches spec; spec is the record of what was built |
| **Deprecated**  | Superseded by a newer spec (link provided)              |

---

## Naming Convention

```
specs/<domain>/<name>.md
```

Examples:

- `specs/ai/agent-design.md`
- `specs/privacy/pii-inventory.md`
- `specs/system/architecture.md`

---

## Ownership Table

| Spec                               | Owner         | Reviewer      | Status   |
| ---------------------------------- | ------------- | ------------- | -------- |
| `specs/system/vision.md`           | Product Owner | Tech Lead     | Approved |
| `specs/system/architecture.md`     | Tech Lead     | SRE Lead      | Approved |
| `specs/system/async-event-flow.md` | Tech Lead     | DevOps Lead   | Approved |
| `specs/api/async-api-design.md`    | Tech Lead     | DevOps Lead   | Approved |
| `specs/ai/agent-design.md`         | AI Lead       | Tech Lead     | Approved |
| `specs/ai/hitl-hotl.md`            | AI Lead       | Security Lead | Approved |
| `specs/ai/guardrails.md`           | Security Lead | AI Lead       | Approved |
| `specs/privacy/pii-inventory.md`   | DPO           | Tech Lead     | Approved |
| `specs/privacy/data-retention.md`  | DPO           | SRE Lead      | Approved |
| `specs/privacy/dpia-ripd.md`       | DPO           | Legal         | Approved |
| `specs/ai/harness-design.md`       | AI Lead       | Tech Lead     | Approved |

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

Refs: #42, SPEC-guardrails, ADR-0012
```

---

## How to Update a Spec

- **Minor clarifications** (no behaviour change): PR by spec owner; single reviewer
- **Major changes** (behaviour or interface change): new ADR required; spec version incremented; PR reviewed by owner + all implementers

When implementation diverges from the spec, the spec must be updated in the same PR
that makes the implementation change — they must stay in sync.
