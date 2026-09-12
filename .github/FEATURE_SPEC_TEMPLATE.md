# Feature Spec: {Feature Name}

> **⚡ Agent-Generated:** This document was drafted by Claude Code on {date}.
> **Human Review Required:** Tech Lead + Security Lead (if security surface changes) must review and approve before implementation begins.
> **Review Status:** Draft
> **Reviewer:** — | **Approved:** —

---

<!-- ADR-0085 frontmatter — REQUIRED. Copy this block to the very top of the file (line 1). -->

```yaml
---
id: SPEC-FEAT-{NNN} # SPEC-<DOMAIN>-<NNN>; the FEAT-{id} directory is the issue alias
kind: feature-spec
status: draft # draft | in-review | approved | implemented | superseded
owner: {name}
issue: {issue-number}
governing_adrs: [] # ADRs that govern this feature
new_adrs_required: []
implemented_by: [] # filled at implementation
verified_by: [] # tests that prove the ACs
related_specs: [docs/product/FEAT-{id}/nfr.md]
last_updated: YYYY-MM-DD
---
```

**FEAT-ID:** FEAT-{id} | **Spec id:** SPEC-FEAT-{NNN} | **Owner:** {name}
**ADR References:** {list ADRs that govern this feature}
**NFR Reference:** `docs/product/FEAT-{id}/nfr.md`
**GitHub Issue:** #{issue-number}
**Sprint:** {sprint-id or milestone}

> This template is a **profile** of `specs/SPEC-TEMPLATE.md` (W13-T8): same lifecycle, same
> FR→AC coverage gate (§11), same Open Questions (§12) and Assumptions (§13) sections.

---

## 1. Goal & Success Metrics

<!-- What does this feature achieve? How will success be measured? -->

### Goal

<!-- One sentence: what the feature does for the user or system. -->

### Success Metrics

| Metric | Baseline | Target | Measurement Method |
| ------ | -------- | ------ | ------------------ |
|        |          |        |                    |

### Business Value Gate

<!-- What observable metric improves because of this feature?
     Required for PRR sign-off (skills/sre/prr.md). -->

- **Baseline metric:** <!-- e.g. HITL queue wait time p50 = 4.2 minutes -->
- **Target:** <!-- e.g. < 1 minute -->
- **Measurement:** <!-- e.g. Prometheus histogram `hitl_wait_seconds` -->

---

## 2. User Stories & Acceptance Criteria

<!-- Functional requirements use EARS phrasing ("WHEN <trigger> the system SHALL <response>"),
     numbered FR-01…; the AC table (id → FR → verification) is the canonical, gate-checked form
     (docs/product/acceptance-criteria-standard.md). Gherkin is an optional companion for
     tests/integration/ scenarios — keep it, but the table is what the coverage footer counts. -->

### Functional Requirements (EARS)

| FR    | Statement                                                | Priority |
| ----- | -------------------------------------------------------- | -------- |
| FR-01 | WHEN {trigger} the system SHALL {response}               | must     |

### Acceptance Criteria (canonical)

| AC    | Covers | Given / When / Then (one line)         | Verified by (test path or `pytest.mark.requirement`) |
| ----- | ------ | -------------------------------------- | ---------------------------------------------------- |
| AC-01 | FR-01  | {given} / {when} / {then}              | `tests/…` — `@pytest.mark.requirement("SPEC-FEAT-{NNN}/FR-01")` |

### Story 1: {title}

**As a** {role},
**I want to** {action},
**so that** {benefit}.

```gherkin
Feature: {feature name}

  Scenario: {happy path}
    Given {precondition}
    When {action}
    Then {expected outcome}
    And {additional assertion}

  Scenario: {error case}
    Given {precondition}
    When {invalid action}
    Then {error response}
```

---

## 3. API Contract Delta (OpenAPI)

<!-- Describe changes to the REST API surface.
     For new endpoints: provide the full OpenAPI path object.
     For modified endpoints: describe the delta only. -->

### New / Modified Endpoints

| Method | Path | Description | Auth Required |
| ------ | ---- | ----------- | ------------- |
|        |      |             |               |

### Request / Response Schema Changes

```yaml
# OpenAPI delta — paste only the changed paths/components
```

> Full spec: `docs/api/openapi/v1/openapi.yaml`

---

## 4. Event Contract Delta (Avro)

<!-- Describe changes to Kafka event schemas.
     New topics must be registered in services.yaml and asyncapi.yaml. -->

### New / Modified Topics

| Topic | Event Type | Producer | Consumer |
| ----- | ---------- | -------- | -------- |
|       |            |          |          |

### Schema Changes

```json
// Avro schema delta — paste only the changed fields
```

> Full schemas: `infrastructure/message-broker/schema-registry/avro/`
> AsyncAPI spec: `docs/api/asyncapi/v1/asyncapi.yaml`

---

## 5. Data Model Changes

<!-- SQLAlchemy model changes and Alembic migration outline. -->

### Model Changes

| Table | Column | Type | Change                |
| ----- | ------ | ---- | --------------------- |
|       |        |      | Add / Remove / Modify |

### Migration Outline

```python
# alembic/versions/{hash}_{slug}.py — outline only; agent generates the full file
def upgrade():
    # e.g. op.add_column('requests', sa.Column('priority', sa.Integer(), nullable=True))
    pass

def downgrade():
    pass
```

---

## 6. Agent Configuration _(if this feature involves the AI Agents Module)_

> Skip this section if `src/agents/` is not involved.

```yaml
# SpecContract for SpecContractEnforcer
spec_contract:
  scope_boundary: "{feature-slug}"
  allowed_action_types:
    - { action-type-1 }
    - { action-type-2 }
  prohibited_operations:
    - { prohibited-1 }
```

- **HITL required:** true / false
- **Autonomy level:** NONE / LOW_RISK / MEDIUM_RISK / FULL
- **New action schemas needed:** yes (add to `infrastructure/agent-tools/action-schemas/`) / no
- **RuntimePolicyGateway rules needed:** yes (update `infrastructure/agent-policies/policies.yaml`) / no

---

## 7. Security & Privacy

### PII Classification

- **New PII fields introduced:** yes / no
- **PII level:** L1 / L2 / L3 / L4 / None
- **Masking enforced by:** `src/guardrails/pii_filter.py` — field names: {list}
- **DPIA/RIPD required:** yes (link: `docs/privacy/dpia/`) / no

### Threat Surface Delta

<!-- Reference specs/security/threat-model.md. List new attack surfaces introduced. -->

| Threat | Category | Mitigation | Residual Risk       |
| ------ | -------- | ---------- | ------------------- |
|        | STRIDE:  |            | Low / Medium / High |

### OWASP Controls Required

<!-- Check which OWASP Top 10 controls apply to this feature. -->

- [ ] A01 Broken Access Control — RBAC enforced; resource ownership validated
- [ ] A03 Injection — parameterized queries only; prompt injection guard on
- [ ] A07 Auth Failures — JWT validated; session expiry enforced
- [ ] LLM01 Prompt Injection — `prompt_injection_guard.py` active _(agents only)_
- [ ] LLM08 Excessive Agency — HITL gateway enforced _(agents only)_

---

## 8. Observability

<!-- Every new code path touching the critical user journey must be instrumented. -->

### New Prometheus Metrics

| Metric Name | Type                        | Labels | Description |
| ----------- | --------------------------- | ------ | ----------- |
|             | counter / gauge / histogram |        |             |

### New OTel Span Attributes

| Span | Attribute | Value Type | Description |
| ---- | --------- | ---------- | ----------- |
|      |           |            |             |

### Grafana Panel Required

- [ ] Yes — update dashboard: `infrastructure/monitoring/grafana/dashboards/{dashboard}.json`
- [ ] No — existing panels cover this feature's critical path

---

## 9. Operational Readiness

### New Failure Modes

| Failure Mode | Detection        | Recovery | Runbook |
| ------------ | ---------------- | -------- | ------- |
|              | Prometheus alert |          | RB-{id} |

### Runbook Required

- [ ] Yes — create `docs/sre/runbooks/RB-{next}-{slug}.md`
- [ ] No — existing runbooks cover this failure mode

### SLO Impact

- **SLO affected:** <!-- e.g. CUJ-001 Request Processing < 2s p99 -->
- **Expected impact:** <!-- e.g. +10ms p99 due to new DB query -->
- **Error budget consumption estimate:** <!-- e.g. negligible / <0.1% -->

### K8s Health Probes

- [ ] `startupProbe` configured for any new Deployment
- [ ] `livenessProbe` configured
- [ ] `readinessProbe` configured
- [ ] Probe lint CI will pass (`ci-k8s-probe-lint.yml`)

---

## 10. Implementation Notes

<!-- Any implementation constraints, ordering dependencies, or rollout considerations
     that the implementing agent should know before starting. -->

### Dependencies

| Dependency | Type                    | Status          |
| ---------- | ----------------------- | --------------- |
|            | Blocking / Non-blocking | Open / Resolved |

### Rollout Strategy

- [ ] Feature flag controlled (flag name: `{flag-name}` in `infrastructure/feature-flags/`)
- [ ] Direct rollout (no flag needed)
- [ ] Canary — define traffic split: {%}

### Rollback Plan

<!-- How to revert this feature if a production incident occurs. -->

```bash
# Rollback steps
make rollback SERVICE={service-name}
```

---

## 11. Requirement Coverage (gate)

<!-- Every FR in §2 MUST map to at least one AC. Any unmapped FR blocks Definition of Ready / Done
     (specs/SPEC-TEMPLATE.md §11 rule; checked at Phase 3 and Phase 4). -->

**Requirement coverage footer (gate).** _N_ FRs total · _M_ mapped to ≥ 1 AC · **_K_ unmapped ⚠️**

---

## 12. Open Questions

<!-- Anything that must be resolved at a HITL gate rather than assumed. Every item must be marked
     resolved/decided/deferred with an ADR, RFC or #issue reference before status: approved —
     enforced by scripts/governance/check_open_questions.py (W11-T5). "None." is a valid body. -->

None.

---

## 13. Assumptions

<!-- Assumptions carried from docs/product/FEAT-{id}/discovery.md and made during specification.
     Each has an owner and the phase by which it must be confirmed or converted into an FR/open
     question. An assumption still unconfirmed at its resolve-by phase is a gate failure. -->

| # | Assumption | Owner | Resolve by (phase) | Status (open / confirmed / rejected) |
| - | ---------- | ----- | ------------------ | ------------------------------------ |
| A1 |            |       | 4 — Specification  | open                                 |

---

_This spec template is pre-populated by Claude Code per the Agentic SDLC Phase 3 workflow.
Full spec lifecycle: `docs/process/WORKFLOW.md` | Spec lifecycle skill: `skills/sdlc/spec-lifecycle.md`_
