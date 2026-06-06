# Spec: Learn Stage — Perceive → Reason → Act → Learn

**Status:** Approved
**Issue:** #15 | **ADR:** ADR-0038
**Owner:** AI Governance Lead | **Last updated:** 2026-06-05

---

## 1. Purpose

Close the fourth stage of Gartner's Agentic Operation Pathway. The orchestrator
currently implements Perceive → Reason → Act. This spec adds the **Learn** stage:
a feedback loop that captures HITL decision outcomes and injects relevant precedents
into future Reason-stage LLM calls.

---

## 2. Data Model

### `OutcomeFeedback`

```json
{
  "feedback_id": "<uuid>",
  "action_id": "<hitl_request_id>",
  "action_type": "send-email",
  "payload_hash": "<sha256 of action_parameters>",
  "decision": "approved | rejected",
  "decision_reason": "<free text from approver rationale>",
  "outcome_signal": "success | failure | unknown",
  "agent_id": "<agent_id>",
  "recorded_at": "<ISO-8601>"
}
```

Storage tag: `learn:outcome` in the vector store (InMemoryVectorStore or PostgresVectorStore).

### `BiasReport`

```json
{
  "rejection_rate": 0.0,
  "approval_rate": 1.0,
  "total_decisions": 0,
  "top_rejected_action_types": ["send-email", "delete-record"],
  "window_days": 30
}
```

---

## 3. Learning Modes

Controlled exclusively by the `learning-mode` OpenFeature flag (default: `passive`).
Changing to `active` requires ADR-0038 governance sign-off.

| Mode      | Behaviour                                                                                        |
| --------- | ------------------------------------------------------------------------------------------------ |
| `passive` | Precedents are stored and surfaced in logs and Grafana only. No LLM injection.                   |
| `active`  | Top-3 precedents are injected into the Reason-stage LLM system prompt as a `[PRECEDENTS]` block. |

### `[PRECEDENTS]` block format (active mode only)

```
[PRECEDENTS]
- action: send-email, prior_outcome: rejected (3/5 times), reason: PII in payload
- action: read-db-record, prior_outcome: approved (5/5 times), reason: read-only, low risk
[/PRECEDENTS]
```

---

## 4. Integration Points

| Integration point                             | What happens                                                                                               |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| After `HITLGateway.record_decision()`         | `FeedbackLearner.record(decision)` stores the outcome                                                      |
| Before `AgentOrchestrator._reason()` LLM call | `FeedbackLearner.get_similar_precedents()` is called; if `active` mode, result injected into system prompt |
| `make agent-feedback-check`                   | Calls `FeedbackLearner.get_bias_summary()` to build the Prometheus report                                  |

---

## 5. Feedback Window

Rolling 30-day window. Outcomes older than 30 days are excluded from precedent
retrieval and bias summary calculations. The vector store TTL enforces this.

---

## 6. Governance Guard

The Learn stage **MUST NOT** modify agent behavior in `passive` mode. In `active` mode,
precedents are injected as informational context only — the LLM may consider them but
they do not override the HITL risk threshold or feature flag controls. Enabling `active`
mode requires an explicit update to `infrastructure/feature-flags/flags/learning-mode.yaml`
and a governance sign-off documented in `docs/ai-governance/dual-use-registry.md`.

---

## 7. Metrics

| Metric                                  | Type    | Labels                              |
| --------------------------------------- | ------- | ----------------------------------- |
| `agent_learn_precedents_injected_total` | Counter | `action_type`, `outcome_influenced` |

---

## 8. Related

- `src/agents/feedback_learner.py` — implementation
- `docs/adr/ADR-0038-learn-stage-feedback-loop.md`
- `infrastructure/feature-flags/flags/learning-mode.yaml`
- `src/agents/orchestrator/orchestrator.py` — integration point
- `src/agents/hitl_gateway.py` — integration point
