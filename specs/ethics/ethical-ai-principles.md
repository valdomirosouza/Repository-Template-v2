# Ethical AI Principles

**Status:** Approved | **Owner:** AI Governance Lead | **Last updated:** 2026-05-28
**Scope:** AI Agents Module — all components under `src/agents/`, `src/guardrails/`, `src/memory/`
**Regulatory context:** EU AI Act (High-Risk, Arts. 9–14), LGPD Art. 20, GDPR Art. 22
**ADR references:** ADR-0011 (HITL/HOTL), ADR-0015 (Feature Flags), ADR-0016 (Sandbox)
**Related:** `docs/ai-governance/eu-ai-act-compliance.md`, `docs/ai-governance/nist-ai-rmf.md`

---

## 1. Core Principles

### 1.1 Human Oversight (Non-Negotiable)

All agent actions with real-world effects require explicit human approval or delegated
authority before execution. This is enforced structurally, not by convention.

**Implementation:**

- `HITLGateway` is the sole execution path for consequential actions — no bypass exists
- Timeout always results in **rejection**, never auto-approval (ADR-0011)
- HOTL mode retains human override capability at all times
- Autonomy escalation beyond `LOW_RISK` requires ADR-0015 governance sign-off

**Compliance mapping:** EU AI Act Art. 14 (human oversight); NIST AI RMF GOVERN 1.1

### 1.2 Transparency

The system must be explainable to operators, data subjects, and regulators.

**Implementation:**

- Every agent action is recorded in the immutable audit log (`audit_logger.py`)
- `DecisionTreeLogger` records branching decisions with rationale
- `ExecutionSummary` attached to every sprint result and HITL escalation
- Model capabilities and limitations documented in `docs/ai-governance/model-card.md`
- Data subjects informed they interact with an AI system (UI disclosure required — REM-001 in `eu-ai-act-compliance.md`)

**Compliance mapping:** EU AI Act Art. 13 (transparency); LGPD Art. 20 (automated decision-making)

### 1.3 Fairness and Non-Discrimination

The system must not produce outputs that discriminate on protected characteristics.

**Implementation:**

- PII masking (`pii_filter.py`) removes demographic identifiers before LLM inference, reducing correlation with protected attributes
- `BugHistoryStore` tracks HITL rejection patterns per `action_type` — monitor for disparate rejection rates across user segments
- The feedback loop (`feedback_loop.py`) adjusts risk scores per `action_type`, not per user identity — bias adjustments must not proxy for demographic characteristics
- Quarterly bias audit: compare HITL approval rates across request origins; flag any p-value < 0.05 for review

**Prohibited patterns:**

- Using `agent_id`, `user_id`, or any user-correlated field as a direct input to risk scoring without explicit governance review
- Training or fine-tuning on HITL decision data without a dedicated bias impact assessment

**Compliance mapping:** EU AI Act Art. 10 (data governance); NIST AI RMF MAP 2.3

### 1.4 Privacy by Design

Personal data is minimised, masked at the earliest opportunity, and never forwarded beyond system boundaries in unmasked form.

**Implementation:**

- L1–L4 PII classification (see `docs/privacy/pii-inventory.md`)
- PII masking is applied before: LLM call, log write, broker publish, vector store write
- Session memory TTL: 24 h (configurable, default enforces data minimisation)
- Data retention: 30 days active, 90 days archived, then deletion (ADR-0013)
- DPIA required for any new PII processing activity (see `specs/privacy/dpia-ripd.md`)

**Compliance mapping:** GDPR Art. 25 (data protection by design); LGPD Art. 46

### 1.5 Accountability

Every decision and action is attributable, auditable, and correctable.

**Implementation:**

- `agent_id` + `trace_id` + `correlation_id` present on every audit event
- HITL decisions include `decided_by` + timestamp + rationale
- Patch proposals logged with `previous_approach_summary` and `proposed_alternative`
- Audit log is immutable — no delete path exists; PostgreSQL `INSERT`-only permissions
- Quarterly governance review of `docs/ai-governance/` by AI Governance Lead

**Compliance mapping:** EU AI Act Art. 9 (risk management); NIST AI RMF GOVERN 6.2

### 1.6 Safety and Robustness

The system must fail safely when it encounters unexpected inputs or infrastructure degradation.

**Implementation:**

- Prompt injection guard rejects on uncertainty (default REJECT, never PASS-THROUGH)
- Circuit breaker on LLM API (`llm_circuit_breaker_threshold=5`) prevents cascading failures
- Sandbox isolation (`docker-compose.sandbox.yml`: `network=none`, read-only FS, resource caps)
- Infrastructure fallbacks (in-memory stores) preserve local development without compromising production safety properties
- Chaos experiments (`tests/chaos/experiments/`) verify safety under failure conditions

**Compliance mapping:** EU AI Act Art. 15 (accuracy, robustness, cybersecurity)

---

## 2. Prohibited Uses

The following uses are unconditionally prohibited regardless of business justification:

| #    | Prohibited use                                                                  | Rationale                            |
| ---- | ------------------------------------------------------------------------------- | ------------------------------------ |
| P-01 | Autonomous actions affecting legal rights or obligations without HITL approval  | EU AI Act Art. 14; irreversibility   |
| P-02 | Inferring or acting on protected characteristics (race, religion, health, etc.) | Anti-discrimination law; GDPR Art. 9 |
| P-03 | Storing unmasked PII in vector store, session memory, or audit log              | Privacy-by-design invariant          |
| P-04 | Disabling or weakening guardrails in any environment                            | Safety invariant; no exceptions      |
| P-05 | Using agent outputs as sole basis for consequential decisions about individuals | Human oversight requirement          |
| P-06 | Enabling `FULL` autonomy without ADR-0015 governance approval                   | Governance invariant                 |

---

## 3. Bias Monitoring Procedure

**Trigger:** Run quarterly or after any change to risk scoring, HITL thresholds, or action type taxonomy.

**Steps:**

1. Export HITL approval/rejection counts from Prometheus by `action_type` for the review period
2. Group by request origin segment (if tracked) — do not group by user identity
3. Compute approval rate per `action_type`; flag any `action_type` with rejection rate > 2× the average
4. If flagged: inspect `BugHistoryStore` rejection reasons; determine if the pattern is spec-driven or model-driven
5. If model-driven: raise a DPIA amendment; consult DPO before adjusting thresholds
6. Record outcome in `docs/ai-governance/` with date and reviewer sign-off

---

## 4. Incident Response for Ethical Violations

If an agent produces output that violates these principles:

1. **Immediately** disable the relevant `action_type` via feature flag
2. Notify AI Governance Lead and DPO within 1 hour
3. Preserve all audit log entries for the affected `correlation_id`
4. File a postmortem in `docs/postmortems/` within 48 hours
5. Conduct root-cause analysis before re-enabling the action type
6. If personal data was exposed: trigger GDPR/LGPD breach notification process (72-hour window)
