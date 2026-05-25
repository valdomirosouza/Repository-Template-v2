# Skill — Critical User Journey (CUJ)

**Owner:** SRE Lead | **Reviewer:** Product Owner | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill when defining, validating, or testing a critical user journey.

---

## What Is a CUJ

A Critical User Journey is a key workflow that a user must be able to complete reliably. It defines:

- The sequence of steps a user takes
- The SLO targets (latency + availability) that make it "good"
- The Grafana dashboard that visualises it
- The E2E tests that validate it in CI

CUJs drive SLO design: every SLO should trace back to at least one CUJ.

---

## How to Identify a New CUJ

Ask: "If this flow were broken, would a user immediately notice and be blocked?"

Criteria for a CUJ:

- It represents a complete unit of user value (submit → receive result)
- It crosses at least one service boundary
- It has a measurable latency and a clear success/failure outcome
- Business or regulatory impact if it degrades (SLO breach matters)

---

## How to Document a CUJ

Use `docs/sre/cuj/CUJ-001-user-request-processing.md` as the template. Create a new file at:

```
docs/sre/cuj/CUJ-<NNN>-<short-description>.md
```

Required sections:

1. **Overview** — one-paragraph description, owner, SLO targets
2. **Happy Path** — numbered steps from user action to result
3. **SLO Definition** — availability target, latency p99 target, measurement window
4. **Dashboard** — Grafana panel link (create this in the same PR)
5. **Failure Scenarios** — what breaks this CUJ and how it degrades
6. **Test Coverage** — link to E2E test file

---

## How to Define SLO Targets

For a new CUJ, determine:

| Dimension    | How to set                                                                       |
| ------------ | -------------------------------------------------------------------------------- |
| Availability | Start at 99.9% unless business case justifies higher; align with contractual SLA |
| Latency p99  | Measure current p99 baseline; set target at 2× baseline or product requirement   |
| Window       | 30-day rolling (default); can use 7-day for early-stage services                 |

Add the SLO to `docs/sre/slo/slo.yaml` in the same PR as the CUJ document.

---

## How to Create the Grafana Dashboard

For each CUJ, create a dedicated panel (or dashboard) showing:

- Request rate for this specific journey
- Error rate (failed completions)
- p50 / p99 latency end-to-end
- SLO compliance % (current window)

Reference the dashboard UID in the CUJ document's Dashboard section. Add the JSON to `infrastructure/monitoring/grafana/dashboards/cuj-dashboards/`.

---

## How to Write E2E Tests

E2E tests for a CUJ must:

- Cover the full happy path from API entry to final output
- Assert on success criteria (correct response, within latency target)
- Use synthetic/test data only — never real PII
- Be placed in `tests/e2e/test_cuj_<NNN>.py`
- Run in CI against staging environment (added to `harness/staging-check.yml`)

The test must reproduce the steps documented in the CUJ's Happy Path section, step by step.
