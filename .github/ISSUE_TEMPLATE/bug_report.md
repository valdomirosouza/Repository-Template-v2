---
name: Bug Report
description: Report a defect or unexpected behaviour
labels: ["bug", "needs-triage"]
assignees: []
---

## Describe the Bug

<!-- Actual behaviour vs expected behaviour -->

**Actual:** <!-- What happened -->
**Expected:** <!-- What should have happened -->

## Referenced Spec

<!-- Path to the spec governing the component with this bug — REQUIRED -->
<!-- e.g. specs/ai/guardrails.md · specs/api/rest-api-design.md · specs/system/async-event-flow.md -->

## Steps to Reproduce

1.
2.
3.

## Environment

| Field       | Value                                                        |
| ----------- | ------------------------------------------------------------ |
| Service     | <!-- e.g. agent-service, api-gateway -->                     |
| Version     | <!-- e.g. 1.2.3 or git SHA -->                               |
| Environment | <!-- staging / production -->                                |
| Trace ID    | <!-- W3C trace ID if available — do NOT include real PII --> |

## Logs / Traces

```
<!-- Paste relevant log lines here. Remove any PII before pasting. -->
```

## Severity

- [ ] **P1 Critical** — production outage or data loss; SLO breach; page on-call immediately
- [ ] **P2 High** — significant feature degradation; error budget burning fast
- [ ] **P3 Medium** — partial feature impact; workaround available
- [ ] **P4 Low** — minor issue; cosmetic or edge case

## Affected SLO

<!-- If this bug causes an SLO breach, list the affected SLO(s) -->
<!-- e.g. api-gateway availability SLO (target ≥ 99.9%) -->

## Step 2 — Validation Checklist

Before starting the fix, the implementer must confirm:

- [ ] Root cause identified and understood
- [ ] Spec reviewed — fix aligns with intended behaviour in `specs/`
- [ ] ADRs reviewed for binding constraints (`docs/adr/`)
- [ ] Relevant skills loaded (CLAUDE.md §4)
- [ ] Fix does not weaken guardrails or security controls (CLAUDE.md §3.2–3.3)
- [ ] DPIA/RIPD flagged if the fix changes how personal data is processed (CLAUDE.md §3.1)

## Definition of Done

- [ ] Bug reproduced with a failing test before the fix
- [ ] Fix implemented following the spec
- [ ] All tests passing, coverage ≥ 80%
- [ ] `CHANGELOG.md` updated under `Fixed`
- [ ] ADR filed if the fix required an architectural decision

## Additional Context

<!-- Screenshots, related issues, links to Grafana dashboards, etc. -->
