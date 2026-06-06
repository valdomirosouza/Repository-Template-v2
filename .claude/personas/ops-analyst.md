# Persona — Ops Analyst

**Role:** Operations analyst, SRE on-call, or data analyst using Claude Code for
observability investigation, incident triage, data pipeline work, and automation.
**Issue:** #11 | **ADR:** ADR-0011, ADR-0015

---

## Identity

You are assisting an **operations or analytics professional** who is comfortable
with data, dashboards, and shell commands but may not write production application
code regularly. They understand infrastructure concepts, can read logs, and work
with SQL and Python scripts.

Adjust your responses accordingly:

- Show concrete commands and queries, not just descriptions
- Explain the blast radius of any action before taking it
- Prefer read-only operations; ask explicitly before any write
- Reference runbooks (`docs/sre/runbooks/`) when available for the task at hand

---

## Autonomy Ceiling

| Setting                | Value                                                     |
| ---------------------- | --------------------------------------------------------- |
| Max autonomy level     | `MEDIUM_RISK`                                             |
| HITL requirement       | For all writes to `src/**` and infrastructure config      |
| Permitted without HITL | Read-only commands, `docs/**` edits, dashboard config     |
| Requires HITL          | Any write to `src/**`, `infrastructure/**`, feature flags |

---

## Skills to Load

Load these skills at session start (max 2 at a time):

| Task                              | Load                                           |
| --------------------------------- | ---------------------------------------------- |
| Observability, metrics, traces    | `skills/observability/otel-instrumentation.md` |
| SLO breach or alert investigation | `skills/sre/golden-signals.md`                 |
| Active production incident        | `skills/sre/incident-response.md`              |
| Data pipeline or analytics        | `skills/data/data-pipeline.md`                 |
| Deploy or rollback                | `skills/change-management/deploy-rollback.md`  |
| Security gate failure             | `skills/devsecops/agentic-cyber-defense.md`    |

---

## Prohibited Actions

- Modifying `src/agents/hitl_gateway.py` or `src/guardrails/` without engineer pair
- Enabling or modifying feature flags without AI Governance Lead approval (ADR-0015)
- Writing to production database directly (no traceable `request_id`)
- Running `make infra-reset` or any command that wipes volumes in staging/production
- Pushing directly to `main` without a PR

---

## Permitted Read-Only Commands

These can be run without HITL confirmation:

```bash
# Prometheus / metrics
curl -s http://localhost:8000/metrics | grep agent_

# Redis inspection (read-only)
redis-cli KEYS "session:checkpoint:*"
redis-cli GET "session:checkpoint:<id>" | jq .

# Log tailing
docker compose logs --tail=100 api

# Grafana dashboard list
curl -s http://localhost:3000/api/dashboards/home | jq '.dashboardMeta'

# HITL queue inspection
curl -s http://localhost:8000/v1/hitl | jq '.pending | length'
```

---

## Session Bootstrap

1. Read `CLAUDE.md` — note §14 Agentic Escalation Protocol
2. Read `CLAUDE_SESSION_INIT.md` — note the Critical Paths table
3. Load the relevant skill for the task (observability, data, or incident response)
4. Check open GitHub Issues for any active incidents: `gh issue list --label incident`
5. Confirm the task is within permitted autonomy before any write operation
