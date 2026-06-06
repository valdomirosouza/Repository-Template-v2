# ADR-0039: Governed Tool Registry

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Issue:** #16
**Related ADRs:** ADR-0011 (HITL/HOTL Model), ADR-0012 (PII Masking), ADR-0016 (Sandbox Execution), ADR-0038 (Learn Stage)

---

## Context

Gartner's Framework Components require robust Tool Integration: tools must be registered,
permissioned, versioned, and audited. Three gaps were identified in the Gartner Agentic AI
Compliance gap analysis (2026-06-05):

- **T1** — Tools are implicit: `action` strings reach `HITLGateway` with no formal registry
  declaring permissions, PII access, rate limits, or risk classification.
- **T2** — No tool versioning or drift detection. External API changes have no detection path.
- **T3** — Audit logger captures HITL decisions, not individual tool invocations. A sequence
  of low-risk tool calls that together constitute high risk has no aggregate visibility.

---

## Decision

Introduce `src/agents/tool_registry.py` implementing `ToolRegistry` (singleton), backed by a
canonical `ToolDefinition` schema, with the following guarantees:

1. **Registration gate:** `ToolRegistry.assert_registered()` is called at the orchestrator
   level before any tool invocation. Unregistered calls raise `UnregisteredToolError` and
   are blocked.

2. **Permission check:** `check_permission(name, autonomy_level)` enforces the tool risk
   vs. autonomy level matrix. Tools with `requires_hitl=True` always return `True` —
   the HITL gateway enforces the gate.

3. **Canonical catalog:** `infrastructure/agent-tools/tools.yaml` is the single source of
   truth for tool definitions. Starter catalog ships with five tools; teams extend it.

4. **Aggregate risk window (Gap T3):** `AuditLogger.log_tool_invocation()` accumulates
   risk weights in a 5-minute rolling deque. If the aggregate exceeds
   `aggregate_risk_threshold` (default: 3.0), the method returns `False` — the orchestrator
   should treat this as a signal to route the next action through HITL.

5. **Metric:** `agent_tool_invocations_total{tool_name, risk_level, outcome}` is incremented
   on every `log_tool_invocation()` call.

---

## Consequences

**Positive:**

- Every agent tool is declared with permissions and PII access before it is reachable
- Aggregate risk window closes the gap where sequences of low-risk calls constitute high risk
- Tool versioning is explicit; a bumped `version` field signals drift to reviewers
- The `default_tool_registry` singleton is replaceable via dependency injection in tests

**Negative:**

- Teams must add tools to `tools.yaml` and re-deploy before an agent can use them
- The aggregate risk window is in-process (deque) — resets on restart; production
  deployments should migrate to Redis for cross-instance aggregation

**Neutral:**

- `UnregisteredToolError` vs. `KeyError`: the distinction lets orchestrators catch tool
  permission errors separately from general programming errors

---

## Alternatives Considered

- **Implicit tool list in settings:** A comma-separated env var of allowed tool names.
  Rejected — no risk classification, PII access, or rate limit metadata.

- **OpenAPI spec as tool catalog:** Use the API's OpenAPI spec to derive the tool list.
  Rejected — OpenAPI covers REST endpoints, not internal agent tool primitives; different
  concern and lifecycle.
