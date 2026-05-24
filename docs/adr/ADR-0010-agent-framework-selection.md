# ADR-0010 — Agent Framework Selection

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** AI Lead, Tech Lead

---

## Context

The system requires a framework for building autonomous AI agents that:

- Support multi-step tool use and reasoning loops
- Provide an explicit integration point for HITL approval before consequential actions
- Expose observability hooks (one span per LLM call, one span per agent action)
- Are Python-native and actively maintained
- Do not create vendor lock-in at the orchestration layer
- Allow the HITL gateway to intercept the Act step without framework workarounds

Several off-the-shelf agent frameworks were evaluated. All introduce abstractions
that obscure the Act step, making HITL integration either impossible without
framework internals or dependent on framework-specific extension points that may
change across versions.

---

## Decision

Implement agents using a **custom modular loop** pattern directly in `src/agents/`,
structured as:

```
Perception → Reason → Act
```

- **Perception:** collect inputs (user query, tool results, memory retrieval from
  vector store, conversation history)
- **Reason:** single LLM call with system prompt, tool definitions, and context;
  LLM provider abstracted behind a `LLMClient` interface in `src/shared/`
- **Act:** execute the selected tool or produce a response; every action with
  real-world effect is routed through `src/agents/hitl_gateway.py` before execution

Multi-agent coordination is handled by `src/agents/orchestrator/orchestrator.py`,
which routes tasks between specialised agents using a `router.py` component.

---

## Consequences

### Positive

- Full control over the agent loop — HITL integration is explicit, not dependent
  on framework internals
- Every Act step is auditable; `audit_logger.py` records all decisions
- LLM provider is swappable via the `LLMClient` interface without changing agent logic
- No transitive dependency on framework release cycles

### Negative / Trade-offs

- More scaffolding code required compared to off-the-shelf frameworks
- Team must maintain the agent loop implementation; no community bug fixes for
  framework internals
- New engineers must learn the custom loop pattern rather than a widely-known framework

---

## Alternatives Considered

**LangChain**
Rejected: heavy abstraction layers make the Act step opaque; HITL integration
requires monkey-patching internal callbacks; difficult to produce a clean audit
trail per LLM call.

**AutoGen (Microsoft)**
Rejected: HITL control model is limited; human feedback is treated as another
agent message rather than a hard execution gate; insufficient for EU AI Act Art. 14
compliance.

**CrewAI**
Rejected: immature enterprise controls at time of evaluation; no native observability
hooks; task routing tightly coupled to framework internals.
