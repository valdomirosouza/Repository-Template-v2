# RFC-NNNN — <Title>

> **Status:** Draft | Under Review | Approved | Rejected | Withdrawn
> **Date:** YYYY-MM-DD
> **Author(s):** @github-handle
> **Reviewers:** Tech Lead, Security Lead _(Normal)_ · TL + SecOps async _(Emergency)_
> **Related Issue:** #NNN
> **Related Spec:** `specs/<path>.md`
> **Change type:** Standard | Normal | Emergency

---

## 1. Context

_Why is this change needed? What problem does it solve? Include any relevant background,
constraints, or prior decisions (link ADRs if applicable)._

## 2. Proposed Change

_Describe exactly what will change: code, config, infrastructure, data, workflows.
Be specific enough that a reviewer can assess risk without reading the code._

## 3. Alternatives Considered

| Option              | Pros | Cons | Why rejected |
| ------------------- | ---- | ---- | ------------ |
| Option A (proposed) | …    | …    | —            |
| Option B            | …    | …    | …            |

## 4. Impact Assessment

| Area            | Impact                          | Notes |
| --------------- | ------------------------------- | ----- |
| API contracts   | None / Breaking / Additive      |       |
| Database schema | None / Migration required       |       |
| PII / Privacy   | None / DPIA required            |       |
| Security        | None / Security review required |       |
| Performance     | None / Benchmarked              |       |
| Observability   | None / New metrics/alerts added |       |
| Feature flags   | None / Gated behind flag        |       |

## 5. Rollout Plan

1. Pre-deploy steps (migrations, config changes, …)
2. Deployment strategy (canary / rolling / blue-green)
3. Smoke test criteria
4. Observation window

## 6. Rollback Plan

_How do we revert if something goes wrong? Include any irreversible steps and how to
mitigate them._

## 7. Timeline

| Milestone               | Target date |
| ----------------------- | ----------- |
| RFC approved            |             |
| Implementation complete |             |
| Staging deploy          |             |
| Production deploy       |             |

## 8. Open Questions

- [ ] Question 1
- [ ] Question 2

---

_Approved by:_ _(signatures go here after CAB review)_
