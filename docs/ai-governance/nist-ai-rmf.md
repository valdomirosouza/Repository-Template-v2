# NIST AI Risk Management Framework (AI RMF 1.0) Mapping

**Owner:** AI Governance Lead | **Last reviewed:** 2026-05-24

---

## Overview

The NIST AI RMF 1.0 organises AI risk management into four core functions:
**Govern → Map → Measure → Manage**. This document maps each function to the
controls and artifacts implemented in this repository.

---

## GOVERN — AI Risk Governance Structure

Establishes policies, processes, roles, and accountability for AI risk management.

| Sub-category                       | Control                                        | Implementation                                                 |
| ---------------------------------- | ---------------------------------------------- | -------------------------------------------------------------- |
| Roles and responsibilities defined | CODEOWNERS maps ownership of all AI components | `.github/CODEOWNERS`                                           |
| AI governance policies documented  | AI governance artifacts maintained             | `docs/ai-governance/`                                          |
| Risk tolerance defined             | SLO targets and error budget policy            | `docs/sre/slo/slo.yaml`, `docs/sre/slo/error-budget-policy.md` |
| Oversight accountability assigned  | AI Governance Lead + DPO named                 | `docs/ai-governance/autonomy-boundaries.md`                    |
| Incident response defined          | Agent failure runbook                          | `docs/runbooks/`                                               |
| Compliance obligations tracked     | EU AI Act checklist, LGPD/GDPR                 | `docs/ai-governance/eu-ai-act-compliance.md`                   |

---

## MAP — AI Risk Context and Identification

Identifies AI risks in context of the specific use case, stakeholders, and environment.

| Sub-category                          | Control                               | Implementation                              |
| ------------------------------------- | ------------------------------------- | ------------------------------------------- |
| Use cases documented                  | Agent design spec                     | `specs/ai/agent-design.md`                  |
| Stakeholders identified               | Data subjects, operators, maintainers | `docs/privacy/dpia/dpia-v1.md` Section 1    |
| Impacted groups identified            | Users, data subjects                  | DPIA Section 2                              |
| Third-party AI components inventoried | Model card per model                  | `docs/ai-governance/model-card.md`          |
| Autonomy boundaries defined           | HITL/HOTL classification              | `docs/ai-governance/autonomy-boundaries.md` |
| Failure modes catalogued              | Known failure modes in model card     | `docs/ai-governance/model-card.md`          |
| Supply chain risks identified         | SBOM generated and signed             | `.github/workflows/sbom.yml`                |

---

## MEASURE — Risk Analysis and Assessment

Analyses, assesses, and tracks AI risks using quantitative and qualitative methods.

| Sub-category                               | Control                                 | Implementation                           |
| ------------------------------------------ | --------------------------------------- | ---------------------------------------- |
| Bias audit process defined                 | Bias audit template and schedule        | `docs/ai-governance/model-card.md`       |
| Performance metrics defined                | Golden Signals + agent-specific metrics | `src/observability/metrics.py`           |
| DPIA completed before high-risk processing | DPIA v1 template                        | `docs/privacy/dpia/dpia-v1.md`           |
| RIPD completed for Brazilian data subjects | RIPD v1 template                        | `docs/privacy/ripd/ripd-v1.md`           |
| Security testing for AI-specific risks     | Defensive validation suite              | `tests/security/test_owasp_llm_top10.py` |
| PII leakage testing                        | Automated assertion tests               | `tests/security/test_pii_leakage.py`     |
| Error budget tracking                      | Burn rate alerts and policy             | `docs/sre/slo/error-budget-policy.md`    |

---

## MANAGE — Risk Treatment and Monitoring

Prioritises and treats AI risks; monitors effectiveness of controls.

| Sub-category                            | Control                                | Implementation                                |
| --------------------------------------- | -------------------------------------- | --------------------------------------------- |
| HITL controls for consequential actions | HITL gateway — hard execution gate     | `src/agents/hitl_gateway.py`, ADR-0011        |
| HOTL monitoring for autonomous flows    | Grafana dashboards + alert routing     | `infrastructure/monitoring/grafana/`          |
| Input validation guardrail              | Structural input validation            | `src/guardrails/prompt_injection_guard.py`    |
| PII masking guardrail                   | Three-point mandatory masking          | `src/guardrails/pii_filter.py`, ADR-0012      |
| Action scope limits                     | Per-agent rate and scope limits        | `src/guardrails/action_limits.py`             |
| Immutable audit trail                   | Append-only audit log                  | `src/guardrails/audit_logger.py`              |
| Incident response for AI failures       | Agent failure runbook                  | `docs/runbooks/`                              |
| Continuous monitoring                   | Golden Signals dashboards + SLO alerts | `infrastructure/monitoring/prometheus/rules/` |
| Chaos engineering                       | Weekly game day playbook               | `tests/chaos/runbooks/game-day-playbook.md`   |
| PRR before production deploy            | Production Readiness Review            | `docs/sre/prr/PRR-TEMPLATE.md`                |
