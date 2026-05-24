# Production Readiness Review (PRR)

**Service:** \<Service Name\>
**Version:** \<Version\>
**Team:** \<Team Name\>
**On-call contact:** \<Name / PagerDuty rotation\>
**PRR date:** \<Date\>
**Target production date:** \<Date\>

---

## 1. Service Overview

| Field                   | Value                                    |
| ----------------------- | ---------------------------------------- |
| Architecture diagram    | `specs/system/architecture.md`           |
| Upstream dependencies   | \<List services this service calls\>     |
| Downstream dependencies | \<List services that call this service\> |
| Data stores             | \<List databases, caches, queues\>       |
| External integrations   | \<List third-party APIs, LLM providers\> |

---

## 2. SLO Readiness

- [ ] `docs/sre/slo/slo.yaml` committed with SLOs for this service
- [ ] SLOs reviewed and approved by SRE Lead
- [ ] Error budget policy acknowledged by team
- [ ] Error budget > 10% (not in freeze state)

**SLO targets for this service:**

| SLO          | Target | Window |
| ------------ | ------ | ------ |
| Availability |        | 30d    |
| Latency p99  |        | 30d    |

---

## 3. Observability Readiness

- [ ] Golden Signals instrumented (`src/observability/metrics.py`)
- [ ] Structured JSON logging implemented (`src/observability/logger.py`)
- [ ] Distributed tracing enabled (`src/observability/otel_setup.py`)
- [ ] Grafana dashboard created and URL recorded here: \_\_\_
- [ ] All CUJs have dedicated dashboards linked from their CUJ files
- [ ] Log schema validated (required fields: trace_id, span_id, service, severity)

---

## 4. Alerting Readiness

- [ ] Burn rate alerts configured in Prometheus rules
- [ ] Alerts routed to on-call (PagerDuty / OpsGenie rotation)
- [ ] Alerts tested: fired and resolved in staging environment
- [ ] Every alert has a runbook URL in its annotation
- [ ] Golden Signals dashboards reviewed by someone outside the authoring team

---

## 5. Operational Readiness

- [ ] Runbook written and reviewed by someone outside the authoring team
- [ ] Rollback procedure documented and tested (`docs/runbooks/rollback-procedure.md`)
- [ ] Disaster recovery plan covers this service (`docs/runbooks/disaster-recovery.md`)
- [ ] On-call rotation updated to include this service
- [ ] Escalation path documented (on-call → Tech Lead → Engineering Manager)

---

## 6. AI / Agent Readiness _(complete if service includes AI agents)_

- [ ] HITL controls active for all production agent actions
- [ ] HOTL monitoring dashboard configured and linked
- [ ] Agent action audit log verified: append-only, queryable, retained per policy
- [ ] Autonomy boundaries documented (`docs/ai-governance/autonomy-boundaries.md`)
- [ ] HITL approval timeout configured and tested (expires = reject, not approve)
- [ ] Agent failure runbook exists and reviewed

---

## 7. Privacy Readiness

- [ ] PII masking validated end-to-end: confirmed no PII in third-party logs or LLM calls
- [ ] DPIA approved and current (`docs/privacy/dpia/dpia-v1.md`)
- [ ] RIPD approved and current (`docs/privacy/ripd/ripd-v1.md`)
- [ ] Data retention lifecycle rules configured and tested in staging
- [ ] Data subject rights mechanisms tested (access, deletion, portability)
- [ ] DPO sign-off obtained for this release

---

## 8. Security Readiness

- [ ] SBOM generated and signed (Syft + Cosign)
- [ ] Container image scan: zero Critical CVEs (`trivy` output attached)
- [ ] SAST: zero CRITICAL/HIGH findings (`semgrep` output attached)
- [ ] DAST completed in staging: zero OWASP Top 10 critical findings
- [ ] Threat model current (`docs/security/threat-model.md`)
- [ ] All secrets managed via secrets manager (no secrets in code or env vars committed)

---

## 9. Capacity Readiness

- [ ] HPA configured with tested scaling thresholds (`helm/templates/hpa.yaml`)
- [ ] Load test completed against production-equivalent data volume (k6 report attached)
- [ ] PodDisruptionBudget set: minimum 2 pods available at all times
- [ ] Multi-AZ pod anti-affinity rules applied
- [ ] Token budget per agent configured and tested (`LLM_TOKEN_BUDGET_PER_REQUEST`)

---

## 10. Approval

All approvers must sign before production deployment proceeds.

| Role               | Name | Approved | Date | Notes                                  |
| ------------------ | ---- | -------- | ---- | -------------------------------------- |
| SRE Lead           |      | ☐        |      |                                        |
| Tech Lead          |      | ☐        |      |                                        |
| Security Lead      |      | ☐        |      |                                        |
| DPO                |      | ☐        |      | Required for any PII processing change |
| AI Governance Lead |      | ☐        |      | Required if AI agents included         |
