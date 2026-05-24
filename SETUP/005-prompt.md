# Prompt 005 — SRE Documentation + Change Management + Runbooks

> **Requires:** Prompt 001 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Section 3 — SRE Journey, Section 1 — Change Management).
> Skip any file that already exists with real content.

---

## Task

Create all SRE, change management, and runbook documentation files with **real, substantive content**.

---

## Part A — SRE (`docs/sre/`)

### `docs/sre/slo/slo.yaml`

SLO/SLI definitions in YAML. Include:

```yaml
# Structure: one SLO block per service
# Fields per SLO: service, sli_type, description, target, window, alert_burn_rates

version: "1.0"
services:
  - name: api-gateway
    slos:
      - name: availability
        sli_type: availability
        description: "Percentage of requests that return a successful response (non-5xx)"
        target: 99.9 # 99.9% = 43.8 min/month error budget
        window: 30d
        alert_burn_rates:
          - window: 1h
            burn_rate: 14.4 # Fast burn: consumes budget in ~2 days
            severity: critical
          - window: 6h
            burn_rate: 6.0 # Slow burn: consumes budget in ~5 days
            severity: warning

      - name: latency_p99
        sli_type: latency
        description: "99th percentile request latency at the API gateway"
        target: 500ms
        window: 30d

  - name: agent-service
    slos:
      - name: hitl_approval_latency
        sli_type: latency
        description: "Time from HITL request creation to human approval decision"
        target: 300s # 5-minute SLO for human reviewers
        window: 30d

      - name: agent_action_error_rate
        sli_type: error_rate
        description: "Percentage of agent actions that complete without error"
        target: 99.5
        window: 30d
```

Populate with at least 3 services (api-gateway, agent-service, event-consumer)
and 2–3 SLOs each covering availability, latency, and error rate.

---

### `docs/sre/slo/error-budget-policy.md`

Error budget policy. Include:

- Definition of error budget (100% minus SLO target, expressed as downtime minutes per window)
- Error budget calculation table for each SLO (target → monthly budget in minutes)
- **Policy tiers by remaining budget:**

| Remaining Budget | Policy                                                                                    |
| ---------------- | ----------------------------------------------------------------------------------------- |
| > 50%            | Normal development velocity; feature work proceeds                                        |
| 25–50%           | Increase monitoring frequency; review recent changes                                      |
| 10–25%           | Feature freeze for the affected service; reliability work prioritised                     |
| < 10%            | Full feature freeze; incident review required; no production deploys without SRE sign-off |
| 0% (exhausted)   | Emergency response; post-mortem mandatory; CAB review before any deploy                   |

- Burn rate alert thresholds (1h fast burn at 14.4×, 6h slow burn at 6×)
- Replenishment: budget resets at the start of each rolling 30-day window
- Review cadence: weekly SRE review of all error budgets
- Escalation path: SRE → Tech Lead → Engineering Manager

---

### `docs/sre/prr/PRR-TEMPLATE.md`

Full Production Readiness Review template. Include all items from Section 3 of the
reference document. Sections:

**1. Service Overview**

- Service name, version, team, on-call contact
- Architecture diagram reference (link to `specs/system/architecture.md`)
- Dependencies (upstream / downstream services)

**2. SLO Readiness**

- [ ] `docs/sre/slo/slo.yaml` committed with SLOs for this service
- [ ] SLOs reviewed and approved by SRE Lead
- [ ] Error budget policy acknowledged by team

**3. Observability Readiness**

- [ ] Golden Signals instrumented (`src/observability/metrics.py`)
- [ ] Structured logging implemented (`src/observability/logger.py`)
- [ ] Distributed tracing enabled (`src/observability/otel_setup.py`)
- [ ] Grafana dashboard created and linked here
- [ ] All CUJs have dedicated dashboards

**4. Alerting Readiness**

- [ ] Burn rate alerts configured in Prometheus
- [ ] Alerts routed to on-call (PagerDuty / OpsGenie)
- [ ] Alerts tested (fired and resolved in staging)
- [ ] Runbook linked from every alert

**5. Operational Readiness**

- [ ] Runbook reviewed by someone outside the authoring team
- [ ] Rollback procedure documented and tested (`docs/runbooks/rollback-procedure.md`)
- [ ] Disaster recovery plan documented (`docs/runbooks/disaster-recovery.md`)
- [ ] On-call rotation updated

**6. AI / Agent Readiness** (if applicable)

- [ ] HITL controls active for all production agent actions
- [ ] HOTL monitoring dashboard configured
- [ ] Agent action audit log verified (immutable, queryable)
- [ ] Autonomy boundaries documented (`docs/ai-governance/autonomy-boundaries.md`)

**7. Privacy Readiness**

- [ ] PII masking validated end-to-end (no PII in third-party logs)
- [ ] DPIA approved (`docs/privacy/dpia/dpia-v1.md`)
- [ ] RIPD approved (`docs/privacy/ripd/ripd-v1.md`)
- [ ] Data retention rules implemented and tested

**8. Security Readiness**

- [ ] SBOM generated and signed
- [ ] Container image scan: zero Critical CVEs
- [ ] SAST: zero CRITICAL/HIGH findings
- [ ] DAST completed in staging: zero OWASP Top 10 critical findings
- [ ] Threat model current (`docs/security/threat-model.md`)
- [ ] Secrets rotated and managed via secrets manager

**9. Capacity Readiness**

- [ ] HPA configured with tested scaling thresholds
- [ ] Load test completed against production-equivalent data volume
- [ ] PodDisruptionBudget set (minimum 2 pods available)

**10. Approval**

| Role               | Name | Approved | Date |
| ------------------ | ---- | -------- | ---- |
| SRE Lead           |      |          |      |
| Tech Lead          |      |          |      |
| Security Lead      |      |          |      |
| DPO                |      |          |      |
| AI Governance Lead |      |          |      |

---

### `docs/sre/prr/prr-checklist.yaml`

Machine-readable version of the PRR checklist. Structure:

```yaml
version: "1.0"
checklist:
  - category: slo_readiness
    items:
      - id: PRR-SLO-001
        description: "slo.yaml committed with SLOs for this service"
        blocking: true
      - id: PRR-SLO-002
        description: "Error budget policy acknowledged by team"
        blocking: true
  - category: observability
    items:
      - id: PRR-OBS-001
        description: "Golden Signals instrumented"
        blocking: true
      ...
```

Include all items from the PRR template above, each with `id`, `description`,
`blocking: true/false`, and optional `evidence_required` field.

---

### `docs/sre/cuj/CUJ-001-user-request-processing.md`

Critical User Journey template. Include all required fields from Section 3:

- **CUJ ID:** CUJ-001
- **Name:** User Request Processing
- **User Role and Goal:** describe the user type and what they are trying to accomplish
- **SLO Target:** availability ≥ 99.9%, p99 latency ≤ 500ms
- **Step-by-step happy path:** numbered steps from user action to system response
- **Linked Grafana Dashboard:** `infrastructure/monitoring/grafana/dashboards/cuj-dashboards/cuj-001.json`
- **Failure Scenarios:**
  - Scenario name | Trigger | Expected degradation behaviour | Recovery action
- **Dependencies:** upstream and downstream services this CUJ relies on
- **Test coverage:** link to E2E test (`tests/e2e/`)

---

## Part B — Change Management (`docs/change-management/`)

### `docs/change-management/README.md`

Full change management process covering all 8 steps from Section 1 of the reference
document. Include:

- Step 1: Issue creation (required fields, GitHub Issue template reference)
- Step 2: RFC for Normal/Emergency changes (file path, review and approval matrix)
- Step 3: Branch and PR (naming convention, PR template reference)
- Step 4: CI/CD pipeline gates (reference Section 2 quality gates table)
- Step 5: Deploy script usage (`deploy.sh` parameters, 5 deploy steps)
- Step 6: Post-deploy tests (smoke tests, Golden Signals check, CUJ validation,
  privacy check)
- Step 7: Rollback procedure (automatic triggers from SLO breach, manual procedure link)
- Step 8: Changelog update (categories, mandatory references)
- Step 9 (bonus): Post-deploy monitoring windows (24h standard, 72h infra,
  DPO sign-off for PII pipeline changes)
- Change type matrix: Standard / Normal / Emergency — triggers, approvers, timeline
- Roles and responsibilities table

### `docs/change-management/RFC-TEMPLATE.md`

Request for Change template. Sections:

- RFC Number, Title, Author, Date, Status
- **Summary:** one-paragraph description of the change
- **Motivation:** why is this change needed? What problem does it solve?
- **Referenced Spec:** link to `specs/*` governing this change
- **Affected Components:** list of services, APIs, or data flows changed
- **Change Type:** Normal / Emergency
- **Estimated Impact:** affected services, users, data flows, downtime (if any)
- **Implementation Plan:** numbered steps; estimated duration per step
- **Rollback Plan:** how to revert if the change fails; RTO target
- **Testing Plan:** what tests validate this change
- **Privacy Impact:** does this change introduce or modify PII processing? (Y/N)
  If yes, DPIA/RIPD reference.
- **Security Impact:** does this change affect the attack surface? (Y/N)
  If yes, security review reference.
- **Acceptance Criteria:** Given / When / Then format
- **Approvals:**

| Role          | Name | Decision | Date |
| ------------- | ---- | -------- | ---- |
| Tech Lead     |      |          |      |
| Security Lead |      |          |      |
| CAB           |      |          |      |

### `docs/change-management/CAB-PROCESS.md`

Change Advisory Board process. Include:

- CAB composition: Tech Lead, Security Lead, SRE Lead, DPO (for privacy changes)
- Meeting cadence: weekly for Normal changes; async within 4h for Emergency changes
- Submission requirements: RFC filed 48h before CAB for Normal; async for Emergency
- Decision options: Approve / Approve with conditions / Defer / Reject
- Emergency change process (abbreviated): notify → async RFC → TL + SecOps approval → deploy → post-mortem
- CAB meeting template (agenda, decision log format)
- Appeals process

---

## Part C — Runbooks (`docs/runbooks/`)

### `docs/runbooks/README.md`

Runbook template in blameless format. Include:

- Purpose of runbooks in this repository
- Runbook template structure:
  - **Runbook ID and Name**
  - **Severity level** (P1 Critical / P2 High / P3 Medium / P4 Low)
  - **Symptoms:** what the on-call engineer observes (alerts, dashboards, user reports)
  - **Impact:** who is affected and how
  - **Immediate mitigation:** step-by-step actions to reduce impact NOW
  - **Root cause investigation:** diagnostic commands and queries to run
  - **Resolution:** steps to fully resolve the issue
  - **Post-incident:** actions after resolution (monitoring window, post-mortem trigger)
  - **Prevention:** long-term fixes or improvements to prevent recurrence
- Blameless principles: focus on systems and processes, not individuals
- Links to all existing runbooks in `docs/runbooks/`

### `docs/runbooks/rollback-procedure.md`

Detailed rollback playbook. Include:

- When to rollback: automatic triggers (error rate > SLO threshold, p99 latency breach,
  availability drop) and manual triggers (on-call decision, CAB instruction)
- **Automated rollback** (triggered by `rollback.sh`):
  - Step 1: Detect SLO breach via Prometheus alert
  - Step 2: `rollback.sh` executes `helm rollback <release> <revision>`
  - Step 3: Smoke tests run automatically post-rollback
  - Step 4: Golden Signals monitored for 10 minutes
  - Step 5: On-call notified of rollback completion
- **Manual rollback procedure** (when automated rollback fails or is insufficient):
  - Step-by-step `helm rollback` commands
  - How to verify the correct revision to roll back to
  - How to check rollback success
  - Escalation if rollback does not restore service
- **Database rollback:** migration rollback procedure (when applicable)
- **Feature flag rollback:** how to disable a feature flag without a deploy
- Post-rollback actions: open incident, notify stakeholders, schedule post-mortem
- RTO target: per service in `docs/sre/slo/slo.yaml`

### `docs/runbooks/disaster-recovery.md`

DR Playbook. Include:

- **RPO / RTO targets** (per service, referencing `slo.yaml`)
- **Disaster scenarios covered:**
  1. Full region / cloud provider outage
  2. Database corruption or data loss
  3. Message broker (Kafka) complete failure
  4. LLM provider API outage
  5. Security incident requiring immediate service shutdown
- **For each scenario:** detection → immediate response → recovery steps → verification
- **DR activation criteria:** who declares a disaster, threshold for escalation
- **Communication plan:** internal (incident channel, executive notification) and
  external (status page update, customer communication)
- **Backup verification:** monthly test procedure to confirm backup integrity
- **DR drill schedule:** quarterly DR drill; results logged in `docs/postmortems/`
- **Contact list:** on-call rotation, cloud provider support, LLM provider support

---

### Validation

After creating all files, confirm:

- All 10 files listed above exist with substantive content
- `docs/sre/prr/PRR-TEMPLATE.md` covers all 10 sections including AI and Privacy
- `docs/sre/prr/prr-checklist.yaml` is valid YAML with all items from the template
- `docs/sre/slo/slo.yaml` covers at least 3 services with 2 SLOs each
- `docs/change-management/README.md` covers all 8 change management steps
- `docs/runbooks/rollback-procedure.md` covers both automated and manual rollback
