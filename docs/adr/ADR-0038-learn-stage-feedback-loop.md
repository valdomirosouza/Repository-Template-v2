# ADR-0038: Learn Stage Feedback Loop

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Issue:** #15
**Related ADRs:** ADR-0011 (HITL/HOTL Model), ADR-0014 (Multi-Agent Harness), ADR-0017 (Agent Memory Architecture), ADR-0037 (Governance Gate)

---

## Context

Gartner's 4-Stage Agentic Operation Pathway defines: Perceive → Reason → Act → **Learn**.
The repository's orchestrator implements the first three stages but has no feedback loop
from HITL decision outcomes back to future agent reasoning.

Three specific gaps (from the Gartner Agentic AI Compliance gap analysis, 2026-06-05):

- **L1** — No outcome evaluation loop: rejected actions don't influence future proposals
- **L2** — No `FeedbackLearner`: `src/memory/` has `bug_history_store` but no precedent store
- **L3** — `make agent-feedback-check` queries Prometheus for bias but does not actuate the agent

Without the Learn stage the repository sits permanently at the Augmentation maturity tier
and cannot safely advance to Autonomy (a long-horizon agent that never learns from rejections
will repeat the same mistakes).

---

## Decision

Introduce `src/agents/feedback_learner.py` implementing the `FeedbackLearner` class, and
integrate it at two points in the request pipeline:

1. **After `HITLGateway.record_decision()`** — store the decision outcome (approved/rejected,
   rationale, payload hash) as an `OutcomeFeedback` record.

2. **Before the Reason-stage LLM call in `AgentOrchestrator._reason()`** — retrieve up to 3
   matching precedents via `get_similar_precedents()` and, when `learning-mode=active`, inject
   them into the LLM system prompt as a `[PRECEDENTS]` block.

The `learning-mode` OpenFeature flag (default: `passive`) controls injection:

| Mode      | Effect                                                                             |
| --------- | ---------------------------------------------------------------------------------- |
| `passive` | Precedents stored; surfaced in logs and Grafana. No LLM injection. Safe default.   |
| `active`  | Precedents injected into Reason-stage system prompt. Requires governance sign-off. |

A `get_bias_summary()` method feeds the existing `make agent-feedback-check` target with
rejection rates and top rejected action types, closing Gap L3.

---

## Consequences

**Positive:**

- Completes the Gartner 4-Stage Pathway — Perceive → Reason → Act → Learn
- Enables advancement toward the Autonomy maturity tier (with context graph, ADR-0041)
- HITL rejection history is now actioned, not just observed

**Negative:**

- In `active` mode, injected precedents influence LLM outputs — requires governance monitoring
- Storage is in-process (list) in this release; production deployments should swap for Redis
  or PostgresVectorStore (ADR-0017) for persistence across restarts

**Neutral:**

- `passive` mode (the default) adds no risk — it is observability only
- The module-level `default_feedback_learner` singleton is replaceable via dependency
  injection in both `AgentOrchestrator` and `HITLGateway`

---

## Alternatives Considered

- **Embed in the existing `feedback_loop.py`:** That module queries Prometheus for bias
  adjustment. Rejected — different concern (risk_score bias vs. precedent context injection).
  Both coexist.

- **Store outcomes in `src/memory/vector_store.py` immediately:** Deferred to avoid
  coupling the Learn stage to the vector-store dependency in this release. The in-process
  store is sufficient for the passive-mode default and testability.
