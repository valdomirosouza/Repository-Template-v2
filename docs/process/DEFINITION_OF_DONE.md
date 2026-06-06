# Definition of Done (DoD)

> **Version:** 1.0.0 | **Last updated:** 2026-06-06
> **Owner:** Tech Lead | **Approver:** Governance Council + Security Lead
> **ADR:** ADR-0052 | **Workflow phase:** Phase 7 — Code Review

A story / PR is **Done** only when **ALL** applicable criteria below are checked. The DoD is global — per-service addenda may only add stricter gates, never relax them (see Q1 decision in `docs/process/RACI.md`).

---

## DoD Checklist

### Implementation

- [ ] All acceptance criteria from the Issue are implemented and verified by tests
- [ ] Unit test coverage ≥ 80% for all changed files (enforced by `pytest-cov` in CI)
- [ ] Integration tests added or updated for any new service boundary
- [ ] Feature spec (`specs/features/FEAT-{id}/feature-spec.md`) updated if implementation deviated from spec

### Security & Privacy

- [ ] Security tests pass: `make test-security-python`
- [ ] Abuse case tests pass if `src/agents/` or `src/guardrails/` touched: `pytest tests/abuse_cases/ -m abuse_case`
- [ ] No hardcoded secrets — pre-commit hooks and `detect-secrets` CI gate both pass
- [ ] No real PII in any changed file (code, tests, fixtures, logs)
- [ ] PII masking applied for any new data fields (run through `pii_filter.py`)
- [ ] DPIA/RIPD review flagged if new PII processing is introduced (CLAUDE.md §3.1)
- [ ] Guardrails unmodified or strengthened — never weakened

### Documentation & Traceability

- [ ] `CHANGELOG.md [Unreleased]` updated with a meaningful entry
- [ ] ADR created or referenced for any architectural decision introduced
- [ ] `services.yaml` updated if a new service, port, or Kafka topic was added
- [ ] Runbook created (`docs/sre/runbooks/RB-{next}-{slug}.md`) if a new operational failure mode is introduced

### Observability

- [ ] Hierarchical OTel spans instrumented on all new code paths in the critical request flow
- [ ] GenAI semantic convention attributes set on any new LLM calls (`skills/observability/otel-instrumentation.md`)
- [ ] New Prometheus metrics added for any new business-critical operation

### Infrastructure

- [ ] K8s health probes configured for any new Deployment (`startupProbe`, `livenessProbe`, `readinessProbe`)
- [ ] `ci-k8s-probe-lint.yml` passes
- [ ] **SBOM generated** (Syft/CycloneDX) and cosign-attested when the change ships a build artifact
- [ ] **Release & rollback strategy documented** — deploy steps + rollback trigger/criteria (ADR-0056) for any production-impacting change

### Release Readiness _(production-impacting changes)_

- [ ] **PRR completed** and signed off (`docs/sre/prr/PRR-TEMPLATE.md`) before release-candidate promotion

### AI Agents Module _(only when `src/agents/` is involved)_

- [ ] All agent actions with real-world effects route through `hitl_gateway.py`
- [ ] New action types have a corresponding schema in `infrastructure/agent-tools/action-schemas/`
- [ ] `RuntimePolicyGateway` rules updated in `infrastructure/agent-policies/policies.yaml` if new action types are introduced
- [ ] **AI Safety & Agent Governance checklist completed** (`docs/ai-governance/ai-safety-checklist.md`, Phase 10 / ADR-0058)

### Review & Merge

- [ ] ≥ 1 human reviewer has approved the PR (not the session author)
- [ ] AI-assisted review (`ci-ai-review.yml`) comment posted and findings addressed or accepted
- [ ] All blocking CI gates green — no bypassed checks
- [ ] Governance labels present if PR touches `autonomous-mode` flag or `hitl_gateway.py`

---

## Per-Service Addenda

Teams may create `services/{name}/DEFINITION_OF_DONE.md` with additional service-specific gates. That file **must** begin with:

```
This file EXTENDS docs/process/DEFINITION_OF_DONE.md.
All global gates apply. Additional gates below:
```

Per-service addenda that attempt to relax a global gate will be blocked by `governance-gate.yml`.

---

## Related

- `docs/process/DEFINITION_OF_READY.md` — criteria for entering a sprint
- `docs/process/DEFINITION_OF_RELEASE.md` — criteria for production promotion
- `docs/process/RACI.md` — who owns and enforces the DoD
- `.github/pull_request_template.md` — DoD embedded in every PR
