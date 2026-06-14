# User Story Map — FEAT-{id}

> **Owner:** Product Owner | **Phase:** 2 (Discovery) | **Status:** Draft | Under Review | Approved
> Copy to `docs/product/FEAT-{id}/user-story-map.md`. When agent-generated, prepend the
> Agent-Disclosure Header (see `docs/product/README.md`).
>
> A story map organises stories by the user's journey (the **backbone**) rather than by a flat
> backlog, so you can slice a coherent walking-skeleton release first and defer the rest.

---

## Backbone — user activities (left → right = time/flow)

| Activity 1: {verb phrase} | Activity 2: {verb phrase} | Activity 3: {verb phrase} |
| ------------------------- | ------------------------- | ------------------------- |
| {task}                    | {task}                    | {task}                    |

## Stories under each activity

Write every story in the canonical form:

```text
As a <persona>,
I want <capability>,
so that <measurable outcome>.
```

### Activity 1 — {name}

- **US-1.1** — As a {persona}, I want {capability}, so that {outcome}. — _Release: MVP_
- **US-1.2** — As a {persona}, I want {capability}, so that {outcome}. — _Release: Later_

### Activity 2 — {name}

- **US-2.1** — As a {persona}, I want {capability}, so that {outcome}. — _Release: MVP_

---

## Release slices

| Slice                      | Stories included | Goal of the slice           |
| -------------------------- | ---------------- | --------------------------- |
| **MVP / walking skeleton** | US-1.1, US-2.1   | {smallest end-to-end value} |
| **Release 2**              | US-1.2           | {next increment}            |

---

## Acceptance criteria → test → evidence

Every acceptance criterion must map to a test and to observable evidence (closes the loop between
product intent, verification, and production observability — see `skills/engineering/testing-strategy.md`
and `skills/observability/otel-instrumentation.md`).

| AC ID | Scenario (Gherkin Given/When/Then) | Test Type   | Test File               | Metric / Log / Trace Evidence    |
| ----- | ---------------------------------- | ----------- | ----------------------- | -------------------------------- |
| AC-1  | {Given… When… Then…}               | unit        | `tests/unit/...`        | {metric name / log field / span} |
| AC-2  | {Given… When… Then…}               | integration | `tests/integration/...` | {metric name / log field / span} |
| AC-3  | {Given… When… Then…}               | e2e         | `tests/e2e/...`         | {CUJ dashboard panel}            |

---

## Related

- `docs/product/templates/problem-framing-canvas.md`
- `docs/product/templates/success-metrics.md`
- `specs/SPEC-TEMPLATE.md` — stories feed the feature spec's User Stories section
