# ADR-0055 — HOTL Operationalization: Monitor, Override Window, Compensation & Reversibility Metadata

**Status:** Accepted
**Date:** 2026-06-06
**Authors:** Valdomiro Souza

---

## Context

The HOTL (Human On The Loop) model in `specs/ai/hitl-hotl.md` says low-risk
reversible actions execute immediately, notify a reviewer within ~60s, and allow a
5-minute override window during which a reviewer can undo the action via a
compensating action. After Waves A–B, the runtime could _route_ an action to HOTL
(ADR-0053) but had **no lifecycle** for what happens after a HOTL action executes:

- no reviewer notification, no SLO on it;
- no override window, no way to request an override;
- no concept of a _compensating action_ to undo an effect;
- the tool catalog had no reversibility metadata, so the system could not tell
  whether an action was safe to run under HOTL at all.

This left a real gap: a "HOTL" action was indistinguishable from a fire-and-forget
autonomous action. The directive (§3) requires HOTL to be a genuine runtime mode.

## Decision

Implement the full HOTL post-execution lifecycle plus the reversibility metadata it
depends on.

### 1. Reversibility metadata in the tool catalog (P1-2)

`ToolDefinition` gains five fields (conservative, fail-closed defaults):

| Field                     | Default | Meaning                                                       |
| ------------------------- | ------- | ------------------------------------------------------------- |
| `reversible`              | `False` | Whether the action can be undone                              |
| `compensating_action`     | `None`  | Name of the tool that reverses this one                       |
| `max_hotl_risk_score`     | `0.0`   | Highest risk score eligible for autonomous HOTL (0 = never)   |
| `allowed_autonomy_levels` | `()`    | Autonomy levels permitted to invoke the tool                  |
| `requires_dual_approval`  | `False` | Two distinct human approvers required (segregation of duties) |

`tools.yaml` becomes the canonical source: `default_tool_registry` now **loads from
`tools.yaml`** (`load_tools_from_yaml`). In production every tool MUST declare the
reversibility fields or startup fails (`ToolCatalogError`); in non-production,
missing fields fall back to the conservative defaults so local dev and tests run
without the file.

### 2. CompensationRegistry (P1-1)

`src/agents/compensation_registry.py` is the reversibility lookup layer over the
tool registry: `is_reversible`, `get_compensating_action`, and the policy gate
`can_run_under_hotl(action, risk)` — which returns False (→ HITL) for unregistered
or non-reversible actions, or actions above the tool's `max_hotl_risk_score`.

### 3. OverrideService (P1-1)

`src/agents/override_service.py` manages the override window and compensation:

```
agent.action.override.requested
  → agent.action.compensation.started
    → agent.action.compensation.succeeded   (compensator ran)
    | agent.action.compensation.failed       (compensator raised → escalation)
agent.action.confirmed                        (window elapsed, no override)
agent.action.escalation.raised                (failed/absent compensation)
```

- Override outside the window → `OverrideWindowExpiredError` (audited).
- Every override records actor, timestamp, and reason in audit metadata.
- A failed or impossible compensation raises `agent.action.escalation.raised` for
  human remediation.

### 4. HOTLMonitor (P1-1)

`src/agents/hotl_monitor.py` is called by the orchestrator after a HOTL action
returns EXECUTED. It opens the override window (via OverrideService) and emits
`agent.action.hotl.notification.sent`, recording latency against the SLO
(`hotl_notification_slo_seconds`, default 60s). Notifier failures are audited as an
SLO breach but never crash the action flow.

### 5. Orchestrator integration

- **Reversibility gate:** in the decision matrix, an action that would run under
  HOTL but fails `can_run_under_hotl` falls back to HITL
  (`oversight_mode="HITL_NON_REVERSIBLE"`). The gate is on by default (built over
  the same catalog the ToolExecutor uses).
- **Lifecycle hook:** when a `hotl_monitor` is injected, a HOTL execution triggers
  `on_hotl_executed` and the result carries a `hotl_action_id`. When no monitor is
  injected, behaviour is unchanged (backward compatible).

## Consequences

### Positive

- HOTL is a real mode: notify-within-SLO, override window, and compensation are implemented and audited.
- Non-reversible actions can no longer slip through HOTL — they require explicit human approval.
- `tools.yaml` is the single canonical catalog, validated at startup; production fails closed on missing reversibility metadata.
- Failed compensations surface as escalation events instead of being lost.

### Negative / Trade-offs

- `default_tool_registry` now reads a file at import (with hardcoded fallback). A malformed catalog fails import in production — intended, but means the file is now load-bearing.
- The override window/compensation state is in-memory in `OverrideService`; durable cross-restart override state (e.g., Redis-backed) is out of scope here.
- The HOTL monitor is opt-in at the orchestrator; wiring it into the request pipeline (lifespan) is a follow-up.

### Neutral

- Compensation execution is delegated to an injected `compensator` callable (e.g., a `ToolExecutor`), so the override service does not itself hold execution authority.
- Notification delivery is an injected `notifier` callable; the default emits only the audit event (no external channel).

## Alternatives Considered

**Infer reversibility from `risk_level`/keywords:** Rejected — reversibility is a
property of the _effect_, not the risk tier. Explicit per-tool metadata is auditable
and unambiguous.

**Block (reject) non-reversible HOTL actions instead of routing to HITL:** Rejected
— a human may legitimately approve a non-reversible action. Falling back to HITL
preserves the capability under explicit human authority.

**Durable override store now:** Deferred — the in-memory window is sufficient for
the single-process reference implementation; a Redis-backed store mirrors the
existing HITL store pattern and can be added when HOTL is wired into the pipeline.

---

## References

- ADR-0011 — HITL/HOTL Model
- ADR-0039 — Governed tool registry
- ADR-0048 — Zero-trust tool registry
- ADR-0053 — Runtime correctness (routing)
- Spec: `specs/ai/hitl-hotl.md` (HOTL Specification, Override Procedure)
- Directive: `Agentic-SDLC-Repository-Improvement-Directive.md` §3 (P1-1, P1-2)
- Issue: #45
