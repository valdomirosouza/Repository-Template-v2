# Retrospective Guide — Dual Cadence

> **Version:** 1.0.0 | **Last updated:** 2026-06-06
> **Owner:** Tech Lead | **ADR:** ADR-0052
> **Source:** agentic-sdlc-open-questions-resolved.md Q4
> **ISO 27001 alignment:** A.5.36 (compliance with policies), A.10.2 (review of security objectives)
> **EU AI Act alignment:** Article 72 (post-market monitoring logging)

---

## Overview — Two Retrospective Cadences

| Cadence                   | Trigger                         | Duration              | Format               | Output                                               |
| ------------------------- | ------------------------------- | --------------------- | -------------------- | ---------------------------------------------------- |
| **Sprint Retrospective**  | End of every sprint (bi-weekly) | 30 min async          | Lightweight template | `docs/process/retrospectives/sprint-{YYYY-MM-DD}.md` |
| **Release Retrospective** | Every production release        | 60–90 min synchronous | Formal template      | `docs/process/retrospectives/release-{version}.md`   |

**Why two cadences?**

- Sprint retros catch frequent, small friction points fast — before they compound.
- Release retros provide a structured review at a meaningful boundary (what we shipped) and satisfy ISO 27001 A.5.36 and EU AI Act Article 72 monitoring obligations at a cadence that maps to observable outcomes.

---

## Sprint Retrospective

### Cadence & Ownership

- **When:** End of each sprint (bi-weekly), within 48h of sprint close
- **Facilitated by:** Tech Lead (rotating facilitator encouraged after 6 months)
- **Participants:** All team members — async-first; synchronous optional
- **Time limit:** 30 minutes total; async responses collected over 24h

### Template

Save as `docs/process/retrospectives/sprint-{YYYY-MM-DD}.md`:

```markdown
# Sprint Retrospective — {YYYY-MM-DD}

> **Sprint:** {sprint-milestone-name}
> **Facilitator:** {name}
> **Participants:** {names}
> **Date:** {YYYY-MM-DD}

---

## What went well? (async — add bullets by EOD)

-
-

## What slowed us down? (async — add bullets by EOD)

-
-

## One action for next sprint

| Action | Owner | Due |
| ------ | ----- | --- |
|        |       |     |

## DORA snapshot (from Grafana)

| Metric               | This Sprint | Target   |
| -------------------- | ----------- | -------- |
| Deployment Frequency |             | ≥ 1/week |
| Lead Time p50        |             | ≤ 24h    |
| Change Failure Rate  |             | < 5%     |
| MTTR p50             |             | < 1h     |

## Security / Compliance notes (Security Lead adds)

_Any abuse case failures, HITL escalations, or guardrail triggers this sprint:_

-
```

### Follow-Through Rules

1. Action items from the sprint retro are created as GitHub Issues with `type: chore` and assigned to next sprint.
2. The DORA snapshot must be filled in — if metrics are missing, that is itself an action item.
3. Zero unresolved `priority: P0` or `priority: P1` issues from this sprint may carry forward without an explicit decision.

---

## Release Retrospective

### Cadence & Ownership

- **When:** Within 5 business days of every production release
- **Facilitated by:** Release Manager (or Tech Lead if no dedicated Release Manager)
- **Participants:** Tech Lead, Security Lead, SRE Lead, Product Owner, and any team members who had significant contributions to the release
- **Time limit:** 60–90 min synchronous (can be async for patch releases)

### Template

Save as `docs/process/retrospectives/release-{version}.md`:

```markdown
# Release Retrospective — v{version}

> **Version:** {version}
> **Release Date:** {YYYY-MM-DD}
> **Facilitator:** {name}
> **Participants:** {names}

---

## Release Summary

| Item                       | Value      |
| -------------------------- | ---------- |
| Issues shipped             | {count}    |
| PRs merged                 | {count}    |
| Lead time (median)         | {duration} |
| Hotfixes post-release      | {count}    |
| Rollbacks                  | {count}    |
| Security findings resolved | {count}    |
| Open security debt items   | {count}    |

---

## What worked well?

_Process, tooling, and collaboration highlights:_

-
-

## What caused friction or delay?

_Root-cause style — what systemic issue did this reveal?_

-
-

## Incidents & Near-Misses

| Incident | Severity | MTTD | MTTR | Root Cause | Action |
| -------- | -------- | ---- | ---- | ---------- | ------ |
|          |          |      |      |            |        |

## HITL & Autonomy Review _(if AI Agents module active)_

| Metric                                             | Count | Notes |
| -------------------------------------------------- | ----- | ----- |
| HITL approvals issued                              |       |       |
| HITL rejections                                    |       |       |
| Autonomy escalations (`[HITL-ESCALATE]` triggered) |       |       |
| Guardrail triggers (PII filter, prompt injection)  |       |       |
| Abuse case regressions                             |       |       |

_Was the current autonomy level (`NONE` / `LOW_RISK` / etc.) appropriate for this release?_

---

## Model Contract Review _(if model contract tests ran)_

| Model | Contract Version | Last Tested | Result                |
| ----- | ---------------- | ----------- | --------------------- |
|       |                  |             | Pass / Fail / Skipped |

---

## DORA Release Metrics

| Metric               | This Release | 3-Release Trend | Target   |
| -------------------- | ------------ | --------------- | -------- |
| Deployment Frequency |              |                 | ≥ 1/week |
| Lead Time p50        |              |                 | ≤ 24h    |
| Change Failure Rate  |              |                 | < 5%     |
| MTTR p50             |              |                 | < 1h     |

_Source: Grafana DORA dashboard (`infrastructure/monitoring/grafana/dora-metrics.json`)_

---

## ISO 27001 / EU AI Act Compliance Notes

_Required for every release per A.5.36 and EU AI Act Article 72:_

- [ ] Security objectives met for this release period
- [ ] No unmitigated CRITICAL findings shipped
- [ ] Agent post-market monitoring log reviewed (if AI Agents module active)
- [ ] Model behavioral drift within acceptable bounds (if model contract tests ran)

_Observations:_

- ***

## Decisions Made at This Retrospective

| Decision | Rationale | Owner | Due |
| -------- | --------- | ----- | --- |
|          |           |       |     |

## Action Items (→ GitHub Issues)

| Issue Title | Type | Priority | Owner | Sprint |
| ----------- | ---- | -------- | ----- | ------ |
|             |      |          |       |        |

---

_Retrospective closed by: {facilitator} on {YYYY-MM-DD}_
```

### Follow-Through Rules

1. Every "Action Item" row must become a GitHub Issue before the retrospective doc is merged.
2. The ISO 27001 compliance checklist must be signed off — incomplete items are escalated to the Security Lead.
3. If Change Failure Rate exceeds 10% or MTTR exceeds 2h for the release, a required process retrospective is triggered within 5 business days per ADR-0028 (DORA metrics).
4. The release retrospective document is stored in `docs/process/retrospectives/` and linked from the GitHub Release notes.

---

## Storage & Access

```
docs/process/retrospectives/
├── .gitkeep
├── sprint-2026-06-13.md      ← Sprint retro (bi-weekly)
├── sprint-2026-06-27.md
└── release-v2.6.0.md         ← Release retro (per version)
```

Retrospective documents are:

- Committed to `main` via PR (no approval required — these are team records, not governance artefacts)
- Never deleted — they are the institutional memory of the team
- Linked from GitHub Release notes for release retrospectives

---

## Related

- `docs/process/SPRINT-TRACKING.md` — sprint board and cadence
- `docs/process/RACI.md` — retrospective ownership
- `docs/sre/dora-report-YYYY-MM.md` — monthly DORA report template
- `skills/sre/dora-metrics.md` — DORA metric definitions
- ADR-0028 — DORA metrics enforcement
