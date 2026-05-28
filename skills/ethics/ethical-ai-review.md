# Skill — Ethical AI Review

**Owner:** AI Governance Lead | **Reviewer:** DPO, Security Lead | **Status:** Active | **Last updated:** 2026-05-28

Activate this skill when:

- Adding a new agent `action_type`
- Changing risk scoring, HITL thresholds, or autonomy levels
- Extending the feedback loop or bias adjustment logic
- Preparing for a governance review or EU AI Act audit
- Any change that affects how agent outputs influence decisions about individuals

Core reference: `specs/ethics/ethical-ai-principles.md`
Regulatory mapping: `docs/ai-governance/eu-ai-act-compliance.md`, `docs/ai-governance/nist-ai-rmf.md`

---

## Pre-Implementation Ethics Review Checklist

Before implementing any AI/agent feature, answer every question. A "No" or "Uncertain" requires escalation before proceeding.

### Human Oversight (EU AI Act Art. 14)

- [ ] Does every new agent action with real-world effects pass through `HITLGateway`?
- [ ] Is there a human override path available at all times (even in HOTL mode)?
- [ ] Does a timeout result in **rejection**, never auto-approval?
- [ ] Is the autonomy level controlled via the `autonomous-mode` feature flag (not hardcoded)?

### Transparency (EU AI Act Art. 13)

- [ ] Is every decision logged in the immutable audit log with `agent_id`, `trace_id`, `correlation_id`?
- [ ] Does the `ExecutionSummary` include a human-readable rationale for the action?
- [ ] If the system makes a decision affecting a data subject, are they informed it is AI-driven (REM-001)?

### Fairness (EU AI Act Art. 10)

- [ ] Does the new feature avoid using `user_id`, `agent_id`, or any user-correlated field as a direct risk input?
- [ ] Are risk bias adjustments applied per `action_type` only — never per user identity?
- [ ] Has a baseline HITL approval rate been measured for this `action_type` before enabling it in production?

### Privacy by Design (GDPR Art. 25, LGPD Art. 46)

- [ ] Is PII masked before: LLM call, log write, broker publish, vector store write?
- [ ] Are new data fields classified (L1–L4) and added to `docs/privacy/pii-inventory.md`?
- [ ] If new PII processing is introduced, has DPIA/RIPD been flagged to the DPO?

### Accountability

- [ ] Does the audit log include `decided_by` + timestamp + rationale for every HITL decision?
- [ ] Are patch proposals logged with `previous_approach_summary` and `proposed_alternative`?
- [ ] Is there no delete path in the audit log?

### Safety

- [ ] Does the prompt injection guard remain active and unweakened?
- [ ] Is sandbox isolation enforced for any agent-executed code?
- [ ] Does the circuit breaker configuration cover the new LLM call path?

---

## Prohibited Uses — Quick Reference

Stop immediately and escalate if any of these apply:

| Code | Prohibited Use                                                                     |
| ---- | ---------------------------------------------------------------------------------- |
| P-01 | Autonomous action affecting legal rights or obligations without HITL approval      |
| P-02 | Inferring or acting on protected characteristics (race, religion, health, etc.)    |
| P-03 | Storing unmasked PII in vector store, session memory, or audit log                 |
| P-04 | Disabling or weakening guardrails in any environment                               |
| P-05 | Using agent output as the sole basis for consequential decisions about individuals |
| P-06 | Enabling `FULL` autonomy without ADR-0015 governance sign-off                      |

Full list with rationale: `specs/ethics/ethical-ai-principles.md §2`

---

## Quarterly Bias Audit Procedure

Run after any change to risk scoring, HITL thresholds, or action type taxonomy. Also run on schedule (quarterly).

```bash
# 1. Export HITL approval/rejection counts from Prometheus
# Query: sum by (action_type, decision) (hitl_decisions_total)
make agent-feedback-check   # convenience target

# 2. Identify flagged action_types (rejection rate > 2× average)
# 3. Cross-reference with BugHistoryStore rejection reasons
# 4. If model-driven pattern found: raise DPIA amendment; consult DPO
# 5. Record outcome in docs/ai-governance/ with date and reviewer sign-off
```

**Grafana dashboards:**

- `agent-supervision.json` — HITL approval/rejection rates by action_type
- `agent-feedback-loop.json` — bias adjustment history

---

## Incident Response for Ethical Violations

If an agent produces output that violates `specs/ethics/ethical-ai-principles.md`:

1. **Immediately** disable the `action_type` via the feature flag dashboard
2. Notify AI Governance Lead and DPO within **1 hour**
3. Preserve all audit log entries for the affected `correlation_id` — do not purge
4. File a postmortem in `docs/postmortems/` within **48 hours**
5. Conduct root-cause analysis before re-enabling
6. If personal data was exposed: start GDPR/LGPD breach notification (72-hour window)

---

## Governance Sign-Off Requirements

| Change                                        | Required approver(s)                                 |
| --------------------------------------------- | ---------------------------------------------------- |
| New `action_type` enabled in production       | AI Governance Lead                                   |
| Autonomy escalation to `MEDIUM_RISK` or above | AI Governance Lead + Tech Lead (ADR-0015)            |
| `FULL` autonomy enabled                       | AI Governance Lead + Tech Lead + DPO                 |
| Changes to HITL threshold values              | AI Governance Lead + Security Lead                   |
| Changes to `pii_filter.py` masking rules      | DPO + Security Lead                                  |
| Changes to `feedback_loop.py` bias formula    | AI Governance Lead                                   |
| Quarterly bias audit outcome                  | AI Governance Lead (sign-off in docs/ai-governance/) |

---

## EU AI Act Compliance Cross-Reference

| Article | Topic                               | Where enforced in this codebase                          |
| ------- | ----------------------------------- | -------------------------------------------------------- |
| Art. 9  | Risk management system              | `src/agents/risk_scorer.py`, ADR-0011                    |
| Art. 10 | Data and data governance            | `src/guardrails/pii_filter.py`, `docs/privacy/`          |
| Art. 11 | Technical documentation             | `docs/ai-governance/model-card.md`                       |
| Art. 12 | Record-keeping                      | `src/guardrails/audit_logger.py` (immutable INSERT-only) |
| Art. 13 | Transparency                        | `DecisionTreeLogger`, `ExecutionSummary`, UI disclosure  |
| Art. 14 | Human oversight                     | `src/agents/hitl_gateway.py` (sole execution path)       |
| Art. 15 | Accuracy, robustness, cybersecurity | Sandbox isolation, circuit breaker, chaos experiments    |

Full compliance matrix: `docs/ai-governance/eu-ai-act-compliance.md`
