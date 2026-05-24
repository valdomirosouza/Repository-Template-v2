# EU AI Act Compliance Checklist

**Scope:** This system incorporates AI agents with autonomous decision-making capabilities.
**Risk classification:** High-Risk (automated decision-making with real-world effects)
**Owner:** AI Governance Lead | **Last reviewed:** 2026-05-24

---

## System Risk Classification

| Criterion                                          | Assessment                                              |
| -------------------------------------------------- | ------------------------------------------------------- |
| Autonomous decision-making with real-world effects | Yes — agents propose and execute actions                |
| Oversight by humans before consequential actions   | Yes — HITL gateway mandatory (ADR-0011)                 |
| Potential impact on individuals                    | Medium — actions affect user data and external services |
| **Classification**                                 | **High-Risk — Arts. 9, 12, 13, 14 apply**               |

---

## Art. 9 — Risk Management System

| Item                                      | Status       | Evidence                                                            |
| ----------------------------------------- | ------------ | ------------------------------------------------------------------- |
| Risk management process documented        | ✅ Compliant | `docs/privacy/dpia/dpia-v1.md`, `docs/ai-governance/nist-ai-rmf.md` |
| Residual risks identified and mitigated   | ✅ Compliant | DPIA Section 3 risk table                                           |
| Testing performed throughout lifecycle    | ✅ Compliant | `tests/security/`, `tests/chaos/`, PRR checklist                    |
| Risk management updated on system changes | In Progress  | Quarterly review cadence defined                                    |
| Known failure modes documented            | ✅ Compliant | `docs/ai-governance/model-card.md`                                  |

---

## Art. 12 — Record-Keeping (Logging)

| Item                                                | Status       | Evidence                                                  |
| --------------------------------------------------- | ------------ | --------------------------------------------------------- |
| Automatic logging of system events enabled          | ✅ Compliant | `src/observability/logger.py`, OTel setup                 |
| Logs retained for minimum required period           | ✅ Compliant | 90 days warm per `docs/privacy/data-retention-policy.md`  |
| Audit trail covers all autonomous decisions         | ✅ Compliant | `src/guardrails/audit_logger.py` — immutable, append-only |
| Audit log integrity protected                       | ✅ Compliant | Append-only storage; write failure blocks action          |
| Logs accessible to competent authorities on request | In Progress  | Access procedure to be documented                         |

---

## Art. 13 — Transparency and Provision of Information

| Item                                           | Status       | Evidence                                                       |
| ---------------------------------------------- | ------------ | -------------------------------------------------------------- |
| Users informed they interact with an AI system | In Progress  | UI/UX disclosure required before launch                        |
| System capabilities documented                 | ✅ Compliant | `docs/ai-governance/model-card.md`, `specs/ai/agent-design.md` |
| System limitations documented                  | ✅ Compliant | Model card "Known failure modes" section                       |
| Instructions for use provided to deployers     | ✅ Compliant | `docs/runbooks/`, `CLAUDE.md`, PRR template                    |
| Contact point identified for questions         | In Progress  | Add to README and UI                                           |

---

## Art. 14 — Human Oversight

| Item                                                | Status       | Evidence                                                     |
| --------------------------------------------------- | ------------ | ------------------------------------------------------------ |
| HITL controls implemented for consequential actions | ✅ Compliant | `src/agents/hitl_gateway.py`, ADR-0011                       |
| HOTL monitoring active for autonomous flows         | ✅ Compliant | Grafana agent-performance dashboard, alert routing           |
| Override mechanism available at all times           | ✅ Compliant | Ops dashboard override; HITL rejection always available      |
| Persons responsible for oversight identified        | ✅ Compliant | `docs/ai-governance/autonomy-boundaries.md`, CODEOWNERS      |
| Oversight persons trained                           | In Progress  | Training programme to be defined                             |
| Auto-approval on timeout is disabled                | ✅ Compliant | Expired HITL requests are rejected, never approved           |
| Escalation from HOTL to HITL defined                | ✅ Compliant | `docs/ai-governance/autonomy-boundaries.md` escalation rules |

---

## Remediation Roadmap

| Item                                     | Owner              | Target date |
| ---------------------------------------- | ------------------ | ----------- |
| UI/UX AI disclosure for end users        | Product Owner      | \<Date\>    |
| Oversight persons training programme     | AI Governance Lead | \<Date\>    |
| Competent authority log access procedure | DPO + SRE Lead     | \<Date\>    |
| Contact point added to README and UI     | Engineering Lead   | \<Date\>    |
