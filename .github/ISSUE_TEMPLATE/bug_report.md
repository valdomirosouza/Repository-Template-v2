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

## Additional Context

<!-- Screenshots, related issues, links to Grafana dashboards, etc. -->
