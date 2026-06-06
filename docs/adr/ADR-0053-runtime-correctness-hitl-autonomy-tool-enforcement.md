# ADR-0053 — Runtime Correctness: HITL Suspend/Resume, Graduated Autonomy, Mandatory Policy & Tool-Registry Enforcement

**Status:** Accepted
**Date:** 2026-06-06
**Authors:** Valdomiro Souza

---

## Context

The orchestrator (`src/agents/orchestrator/orchestrator.py`) is the critical path
that turns an LLM-proposed action into a real-world effect. An audit against the
_Agentic SDLC Repository Improvement Directive_ (§2) surfaced four P0 runtime
correctness gaps where the implemented behaviour did not match the documented
governance contract:

- **P0-1 — HITL execution flow was broken.** The orchestrator called
  `submit_for_approval()` (which synchronously returns a `PENDING` request) and
  then immediately asserted `status == APPROVED`. Because a human has not yet
  decided at that instant, the check was _always_ false, so **every** HITL-required
  action failed with a `ValueError` instead of suspending and waiting for a human
  decision. HITL was effectively a deny-all gate.

- **P0-2 — Autonomy was a boolean.** `is_autonomous_mode_enabled()` collapsed the
  six documented autonomy levels (`NONE → READ_ONLY → TESTS_ONLY → LOW_RISK →
MEDIUM_RISK → FULL`, ADR-0015) into an on/off switch. The graduated
  `get_autonomy_level(action_type, risk_score)` API existed in `feature_flags.py`
  but was unused on the critical path.

- **P0-3 — No mandatory HITL policy.** Routing depended entirely on the numeric
  risk score. Because the score is keyword-derived, an action could be named to
  dodge a mandatory category (e.g. `adjust_user_state` instead of `delete_user`)
  and receive a low score, downgrading a high-consequence action to autonomous
  execution.

- **P0-4 — The governed tool registry was not enforced at runtime.** A canonical
  registry (`tool_registry.py`, ADR-0048) and `tools.yaml` existed, but the
  orchestrator executed actions directly without asserting registration,
  autonomy-level permission, sandbox routing, rate limits, or owner metadata.

These gaps meant the runtime did not honour the HITL/HOTL model (ADR-0011), the
graduated autonomy model (ADR-0015), or the zero-trust tool registry (ADR-0048).

---

## Decision

Make the orchestrator's **Act** phase a faithful, fail-closed implementation of
the governance contract. Four coordinated changes:

### 1. HITL suspend/resume (P0-1)

A `PENDING` response from the HITL gateway is a **valid suspension state**, not a
failure. The orchestrator returns an application-level response and stops:

```json
{
  "status": "waiting_for_human_approval",
  "hitl_request_id": "<uuid>",
  "action_type": "<action>",
  "risk_score": 0.82,
  "outcome": "PENDING",
  "oversight_mode": "HITL_MANDATORY"
}
```

`REJECTED` and `EXPIRED` raise `ValueError`. Only `APPROVED` falls through to
execution. The action resumes when `POST /v1/hitl/{id}/decide` delivers a decision.

### 2. Graduated autonomy (P0-2)

`is_autonomous_mode_enabled()` is replaced on the critical path by
`get_autonomy_level(action_type, risk_score)`. The orchestrator evaluates the full
ladder and records the resolved `autonomy_level` and `oversight_mode` in the audit
record and OTel span.

### 3. Mandatory HITL policy layer (P0-3)

New module `src/agents/action_policy.py` exposes
`requires_mandatory_hitl(action_type, parameters) -> (bool, reason)`, evaluated
**before** the numeric risk score. A numeric score can never downgrade a mandatory
category. Mandatory categories: external data exfiltration, financial transactions,
credential/secret rotation, production DB writes, production deployments, feature-flag
changes affecting autonomy, bulk operations above threshold, and sandbox-escape
attempts. The triggering reason is persisted in audit metadata.

### 4. Tool-registry runtime enforcement (P0-4)

New module `src/agents/tool_executor.py` is the single choke-point between the
routing decision and execution. Its `execute()` runs a 10-step sequence:

1. Normalize action name (lowercase, hyphens)
2. **Assert the tool is registered** — unregistered → `ToolNotRegisteredError` (blocked, audited)
3. Validate parameters against the tool schema
4. Check `requires_hitl` (short-circuit to `HITL_REQUIRED`)
5. Check the autonomy level permits the tool's risk level
   - 5b. Enforce per-tool per-minute / per-hour rate limits
6. Route sandbox-required tools through `SandboxExecutor`; block direct bypass
7. Execute (sandbox or direct)
8. Emit pre-execution audit (`agent.action.executing`)
9. Emit post-execution audit (`agent.action.executed`) — includes execution mode + owner team
10. Emit failure audit (`agent.action.failed`) on error

### Reconciling the two gates

The orchestrator owns the **routing** decision; the executor owns **enforcement**.
To avoid contradiction after a human approves an action that exceeds the current
autonomy ceiling, `execute()` accepts `hitl_approved: bool`. When `True`, steps 4
and 5 are treated as satisfied (a human reviewer is the highest authority).
**Registry (step 2) and sandbox (step 6) enforcement are never skipped, even after
approval** — registration and sandbox isolation are absolute.

The orchestrator's decision matrix:

| Condition                                 | Route   | Oversight mode         |
| ----------------------------------------- | ------- | ---------------------- |
| `requires_mandatory_hitl` is true         | HITL    | `HITL_MANDATORY`       |
| Tool is **not registered**                | block   | `BLOCKED_UNREGISTERED` |
| `risk_score ≥ hitl_risk_threshold`        | HITL    | `HITL`                 |
| Autonomy level permits the tool           | execute | `HOTL_<level>`         |
| Otherwise (autonomy ceiling insufficient) | HITL    | `HITL`                 |

---

## Consequences

### Positive

- HITL actually suspends and resumes — the HITL/HOTL model (ADR-0011) works end-to-end.
- Six autonomy levels are honoured at runtime; enabling a level has a real, graduated effect.
- High-consequence actions cannot be downgraded by action naming or a low numeric score.
- Every executed action is provably a registered tool, within its autonomy ceiling, rate-limited, and sandbox-isolated where required (ADR-0048) — fail-closed by default.
- Audit records now carry `autonomy_level`, `oversight_mode`, `mandatory_hitl` + reason, execution mode, and owner team.

### Negative / Trade-offs

- The example/abstract action names previously accepted by the orchestrator (e.g. `summarise`, `read_file`) are now rejected unless registered. Tests and demos must use registered starter-catalog tools (`read-db-record`, `write-db-record`, …).
- At the safest default (`NONE` autonomy) **every** action routes to HITL — correct, but it means autonomous execution requires explicitly enabling an autonomy flag (governance-gated, ADR-0015).
- Unparseable LLM output yields `action="unknown"`, which is unregistered and therefore blocked (fail-closed) rather than silently degrading.

### Neutral

- The HOTL post-execution lifecycle (notification, override window, compensation) is **not** in scope here — tracked separately (HOTL monitor / compensation registry).
- `tools.yaml` remains the canonical catalog; loading it into the registry at startup is unchanged by this ADR (the built-in starter catalog still seeds the default registry).

## Alternatives Considered

**Keep boolean autonomy, add registry checks only:** Rejected — leaves P0-2 unaddressed; the graduated model already exists and is governance-approved (ADR-0015).

**Make `tool_executor` route to HITL on permission denial itself:** Rejected — the executor cannot own the HITL gateway without coupling enforcement to routing. The orchestrator pre-checks registration + permission and decides routing; the executor enforces. The `hitl_approved` flag keeps the two gates consistent.

**Treat `PENDING` as success and execute optimistically:** Rejected — defeats the purpose of HITL. Suspension is the correct semantic; execution must wait for an explicit human decision.

---

## References

- ADR-0011 — HITL/HOTL Model
- ADR-0015 — Feature Flag Strategy (graduated autonomy)
- ADR-0016 — Sandbox execution for agent-generated code
- ADR-0048 — Zero-trust tool registry
- Spec: `specs/ai/hitl-hotl.md`
- Directive: `Agentic-SDLC-Repository-Improvement-Directive.md` §2 (P0-1–P0-4)
- Issue: #43
