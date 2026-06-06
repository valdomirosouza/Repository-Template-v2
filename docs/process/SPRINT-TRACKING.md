# Sprint Tracking — GitHub Issues + Projects

> **Version:** 1.0.0 | **Last updated:** 2026-06-06
> **Owner:** Tech Lead | **ADR:** ADR-0052
> **Source:** agentic-sdlc-open-questions-resolved.md Q3

---

## Decision: GitHub Issues + GitHub Projects (native)

Sprint tracking uses **GitHub Issues as the canonical unit of work** and **GitHub Projects (Projects v2)** as the board. No external tool (Jira, Linear, etc.) is required. This keeps the full lifecycle — code, spec, review, tracking — in one system with native cross-linking.

**Rationale:** Every Issue already carries the PR link, spec reference, and label state. A Projects board over those Issues is zero-duplication. Teams that already use an external tracker may mirror Issues there, but GitHub remains the source of truth.

---

## Issue Lifecycle

```
Open (Backlog)
  └─ status: discovery      ← Feature request created; discovery artefacts being authored
      └─ status: ready      ← DoR checklist passed at Grooming Ceremony
          └─ status: in-progress   ← Assigned to sprint; development started
              └─ status: in-review  ← PR open; code review and CI gates running
                  └─ status: done   ← PR merged; all DoD criteria met
                      └─ Closed     ← Issue closed automatically by pr-governance workflow
```

Label transitions are automated by `.github/workflows/issue-lifecycle.yml`:

- PR opened referencing Issue → `status: in-review` applied
- PR merged referencing Issue → `status: done` applied + Issue closed

---

## GitHub Projects Board — 5 Views

The project board is defined in `.github/project-board-definition.json`.

### View 1 — Backlog

| Column    | Filter                      |
| --------- | --------------------------- |
| Discovery | `label:"status: discovery"` |
| Ready     | `label:"status: ready"`     |
| Blocked   | `label:"status: blocked"`   |

**Purpose:** Product Owner manages feature funnel. Grooming ceremony moves Issues from Discovery → Ready.

### View 2 — Sprint Board

| Column             | Filter                                              |
| ------------------ | --------------------------------------------------- |
| In Progress        | `label:"status: in-progress"`                       |
| In Review          | `label:"status: in-review"`                         |
| Done (this sprint) | `label:"status: done"` + milestone = current sprint |

**Purpose:** Daily standup reference. Visualizes WIP per sprint milestone.

### View 3 — Security Debt

| Column   | Filter                                  |
| -------- | --------------------------------------- |
| CRITICAL | `label:"security" label:"priority: P0"` |
| HIGH     | `label:"security" label:"priority: P1"` |
| Backlog  | `label:"security"` (all others)         |

**Purpose:** Security Lead reviews weekly. CRITICAL items block release per DoR-Release.

### View 4 — Release Tracker

| Column              | Filter                              |
| ------------------- | ----------------------------------- |
| This Release        | Issues in current release milestone |
| Pending DoR-Release | PRs with `rc-pending` label         |
| Approved            | PRs with `rc-approved` label        |

**Purpose:** Release Manager tracks release readiness. Feeds into DoR-Release checklist.

### View 5 — DORA Dashboard

A read-only view showing:

- **Deployment Frequency:** count of `status: done` Issues closed per week
- **Lead Time:** `created_at` → PR merge timestamp (estimated from label transitions)
- **Change Failure Rate:** count of `type: hotfix` Issues / total deploys
- **MTTR:** time from `priority: P0` opened → closed

> Note: for precise DORA metrics, use the Grafana DORA dashboard (`infrastructure/monitoring/grafana/dora-metrics.json`) which reads from Prometheus. The Projects view is for quick team visibility only.

---

## Sprint Structure

| Activity              | Cadence     | Duration     | Artifact                                                       |
| --------------------- | ----------- | ------------ | -------------------------------------------------------------- |
| Grooming Ceremony     | Weekly      | 60 min       | Issues moved to `status: ready`                                |
| Sprint Planning       | Bi-weekly   | 60 min       | Sprint milestone created; Issues assigned                      |
| Daily Standup         | Daily       | 15 min       | Sprint Board View 2 reviewed                                   |
| Sprint Review         | Bi-weekly   | 30 min       | Demo of `status: done` Issues                                  |
| Sprint Retrospective  | Bi-weekly   | 30 min async | Retrospective doc in `docs/process/retrospectives/`            |
| Release Retrospective | Per release | 60–90 min    | Formal retrospective per `docs/process/RETROSPECTIVE-GUIDE.md` |

---

## Team-Size Decision Guide

Different team sizes require different levels of process rigour.

### Tier 0 — Solo / 1–5 Engineers

**What to activate:**

- GitHub Issues with basic labels (`type:`, `priority:`, `status:`)
- Sprint Board (View 2) only — skip the other views
- Bi-weekly retrospective (async, 15 min)

**What to skip:**

- Grooming Ceremony → replace with ad-hoc Issue triage
- Formal sprint planning → rolling backlog is fine
- Release Tracker view → use milestone page directly

### Tier 1 — Small Team / 6–20 Engineers

**What to activate:**

- All 5 board views
- Weekly Grooming Ceremony
- Bi-weekly sprint cycle with formal planning
- DoR checklist enforced at Grooming

**What to skip:**

- CAB for Standard Changes → Tech Lead solo approval is sufficient
- Formal PRR → SRE checklist in PR description is enough

### Tier 2 — Medium Team / 21–50 Engineers

**What to activate:**

- All Tier 1 features
- Full CAB for Normal and Emergency changes (ISO 27001 §11)
- Formal PRR (`skills/sre/prr.md`) for all new services
- Security Debt view reviewed by Security Lead weekly

**What to skip:**

- SOX controls — unless org is SEC-listed

### Tier 3 — Large Team / 50+ Engineers

**What to activate:**

- All Tier 2 features
- SOX controls if applicable (`skills/compliance/sox.md`)
- Dedicated Release Manager role
- DORA Dashboard view actively monitored with monthly reports
- Governance Council formal review of DoD/DoR changes

---

## Label Taxonomy

```yaml
# Type labels
type: feature
type: bug
type: chore
type: spike
type: security
type: hotfix

# Status labels
status: discovery
status: ready
status: in-progress
status: in-review
status: done
status: blocked

# Priority labels
priority: P0   # Production incident / blocker
priority: P1   # High — blocks release
priority: P2   # Medium — sprint backlog
priority: P3   # Low — nice to have

# Change management labels (ISO 27001)
standard-change
normal-change
emergency-change

# Governance labels
rc-pending
rc-approved
no-spec
skip-changelog
```

---

## Related

- `.github/workflows/issue-lifecycle.yml` — label automation
- `.github/project-board-definition.json` — board configuration
- `docs/process/DEFINITION_OF_READY.md` — DoR checklist (Grooming gate)
- `docs/process/RETROSPECTIVE-GUIDE.md` — retrospective templates
- `docs/process/RACI.md` — sprint tracking ownership
