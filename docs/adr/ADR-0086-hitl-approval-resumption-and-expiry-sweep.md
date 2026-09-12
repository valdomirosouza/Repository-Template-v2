# ADR-0086 — HITL Approval Resumption and Expiry Sweep

**Status:** Accepted
**Date:** 2026-09-12
**Authors:** Security Lead · AI Governance Lead (drafted with Claude Code, Wave 12 · W12-T2, issue #355)
**Spec:** specs/ai/hitl-hotl.md
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0011](ADR-0011-hitl-hotl-model.md), [ADR-0016](ADR-0016-agent-sandbox-execution-policy.md), [ADR-0039](ADR-0039-governed-tool-registry.md), [ADR-0046](ADR-0046-hitl-trace-linking-guardrail-events.md), [ADR-0089](ADR-0089-documented-capability-reachability-invariant.md)

---

## Context

`HITLGateway.record_decision` published `agent.action.approved` / `agent.action.rejected` and
`expire_stale_requests` published `agent.action.expired`, but no component consumed any of the
three topics. The request consumer wrote the domain request as `completed` the instant the
orchestrator returned `waiting_for_human_approval`. Consequently a human approval was recorded
and audited, and nothing executed; `GET /v1/requests/{id}` reported `completed` for a request
that did nothing; and expiry ran only when a decision happened to hit an expired request
(`ACTIVE_HITL_REQUESTS` never decremented for the rest).

Constraint: `src/agents/hitl_gateway.py` is a dual-approval surface (CLAUDE.md §8, §14.1). The
fix must not weaken it and, ideally, must not modify it.

## Decision

We will close the loop **without changing the gateway**:

1. A new worker, `src/workers/approval_consumer.py`, consumes the three outcome topics. On
   `approved` it resolves the archived `HITLRequest` through `HITLGateway.get_request` and
   executes the action through `ToolExecutor.execute(..., hitl_approved=True)`. Registry and
   sandbox enforcement are never skipped — only the HITL/autonomy checks the human has just
   satisfied (this is the existing `hitl_approved` contract, ADR-0039).
2. The domain request suspended on a HITL request is found via a new
   `RequestStore.get_by_hitl_request_id` (in-memory index / Redis `hitl_link:` key written when
   a `waiting_for_human_approval` state is saved) and moved to an honest terminal status:
   `completed`, `failed`, `rejected` or `expired`. `RequestState.status` gains those values.
3. The request consumer stores `waiting_for_human_approval`, never `completed`, for a suspended
   run.
4. The lifespan schedules `expire_stale_requests()` every `hitl_expiry_sweep_seconds`
   (default 60), so timeouts are enforced by the clock, not by the next decision.
5. `InMemoryBroker` gains `subscribe`, so the loop closes identically without Kafka.
6. Every outcome is audited: `agent.action.executed` / `agent.action.failed` with
   `hitl_request_id`, `sandbox_used` and `hitl_approved: true` in metadata (ADR-0046 linkage).

## Consequences

### Positive

- Human approval has an effect. The template's headline control is real end-to-end.
- Request status is truthful at every step, which the operator UI and the e2e CUJ-002 assert.
- Expiry is time-driven; the pending gauge is accurate.

### Negative / Trade-offs

- A second consumer group (`<group>-approvals`) to operate and monitor; it reuses the consumer
  heartbeat metric.
- Execution after approval runs with the autonomy label `HITL_APPROVED`; tools that are
  unregistered or sandbox-violating still fail (by design) and the request becomes `failed`
  with the reason — operators must read the result, not assume approval implies success.

### Neutral

- The gateway file is untouched; the ADR-0034 dual-approval trigger is not fired by this change
  (`[HITL-NOTE]` recorded in the PR).

## Alternatives Considered

- **Resume inside the orchestrator by re-running the request after approval.** Rejected: it
  would re-run perception and reasoning and could propose a different action than the one
  approved.
- **Execute directly from the `/v1/hitl/{id}/decide` handler.** Rejected: puts tool execution
  on the API request path and bypasses the event contract (`specs/api/async-api-design.md`).
- **Modify the gateway to call the executor.** Rejected: dual-approval surface, and the gateway
  should stay a decision recorder, not an executor.

## Compliance & Risk

- **Controls affected:** GenAI LLM08 (excessive agency) — strengthened: execution still passes
  registry + sandbox; ASVS audit logging — every outcome audited.
- **Data classification impact:** none; `action_parameters` were already stored by the gateway.
- **Autonomy impact:** none. No feature flag changes; approvals do not raise the autonomy level
  (ADR-0015).
- **Review/expiry:** permanent.

---

## Related

- Seven-Axis Review §3 (2026-09-12) · Template v2 Improvement Plan W12-T2
- `tests/integration/test_lifespan_wiring.py`, `tests/e2e/test_hitl_operator_ui.py`
