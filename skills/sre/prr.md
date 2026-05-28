# Skill — Production Readiness Review (PRR)

**Owner:** SRE Lead | **Reviewer:** Tech Lead | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill before any production deployment.

---

## When a PRR Is Required

A PRR is mandatory before every production deploy, including:

- New service going to production for the first time
- Major version release (breaking changes, new features)
- Infrastructure change affecting production (Kubernetes, Kafka, DB schema)
- Any change that modifies `src/guardrails/` or `src/agents/hitl_gateway.py`

Minor patches and hotfixes still require PRR, but may use the abbreviated emergency checklist.

---

## How to Complete the PRR

### Step 1 — Fill the Machine-Readable Checklist

File: `docs/sre/prr/prr-checklist.yaml`

Mark each item `completed: true`. Items with `blocking: true` must all be complete before deploy.

Key blocking sections:

- **PRR-SLO**: SLO targets defined and dashboard exists
- **PRR-OBS**: Metrics, traces, and alerts wired up
- **PRR-SEC**: SAST clean, secrets rotated, guardrails tested
- **PRR-PRIV**: DPIA/RIPD approved by DPO (if new PII processing)
- **PRR-AI**: HITL gateway tested, audit logger verified, action limits set

### Step 2 — Fill the Human-Readable Template

File: `docs/sre/prr/PRR-TEMPLATE.md`

Copy the template, rename to `docs/sre/prr/PRR-<service>-<version>.md`, and complete all 10 sections including the approval table at the bottom.

### Step 3 — Collect Sign-offs

Required approvers before deploy:

| Role               | Signs off on                                         |
| ------------------ | ---------------------------------------------------- |
| Tech Lead          | Architecture, spec compliance                        |
| SRE Lead           | SLO, observability, runbooks                         |
| Security Lead      | SAST, guardrails, secrets                            |
| DPO                | Privacy impact, DPIA/RIPD (if applicable)            |
| AI Governance Lead | HITL coverage, audit completeness (if agent changes) |

Sign-offs are recorded in the PRR document's approval table. All approvers must sign before the deploy workflow is triggered.

### Step 4 — Reference in PR

Add to the PR description:

```
PRR: docs/sre/prr/PRR-<service>-<version>.md
```

The `harness/release-check.yml` gate will verify all blocking PRR items are marked complete.

---

## Common PRR Blockers and Resolutions

| Blocker                    | Resolution                                                                             |
| -------------------------- | -------------------------------------------------------------------------------------- |
| Coverage < 80%             | Add missing unit tests; re-run `make test`                                             |
| No SLO dashboard           | Create Grafana dashboard; update `docs/sre/slo/slo.yaml`                               |
| DPIA not approved          | Submit to DPO with 5 business days lead time                                           |
| SAST HIGH findings         | Fix or document accepted risk with Security Lead sign-off                              |
| No runbook for new service | Create `docs/runbooks/<service>.md` using the template                                 |
| HITL not tested            | Write integration test that exercises the approval flow                                |
| TLS not verified           | Confirm `REDIS_TLS_ENABLED=true` and `rediss://` URL; verify Ingress TLS cert is valid |
| Encryption key missing     | Set `DB_ENCRYPTION_KEY` in Vault; confirm `db_encryption_enabled=true`                 |
| Cert expiry < 30 days      | Trigger manual renewal; see `docs/sre/runbooks/cert-rotation.md`                       |

---

## Emergency PRR (Hotfix)

For P1 hotfixes where time is critical:

1. Complete only the **blocking** items in `prr-checklist.yaml`
2. Get sign-off from Tech Lead + SRE Lead (minimum two approvers)
3. File full PRR retrospectively within 24 hours
4. Post-mortem scheduled automatically for P1 incidents
