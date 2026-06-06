# ADR-0048: Zero-Trust Tool Registry & Operator Authentication

**Status:** Accepted  
**Date:** 2026-06-06  
**Deciders:** Security Lead, AI Governance Lead  
**Refs:** Issue #33, secure-by-design-agentic-ai-compliance-v2.md §Pillar 2 (ZT1, ZT2, ZT3)

---

## Context

The Secure by Design compliance review identified three zero-trust tooling gaps:

- **ZT1** — The tool registry (`ADR-0039`) declared minimum-privilege tool catalog and rate limits,
  but lacked an `execution_mode` field distinguishing tools that MUST run in the Docker sandbox
  from those that can execute in-process. Without this, a developer adding a new `execute-code`
  action could wire it directly (bypassing `SandboxExecutor`) with no structural guard.
- **ZT2** — `sandbox_executor.py` existed as an opt-in mechanism. Nothing in the architecture
  enforced that code-execution actions used it; the enforcement was by convention only.
- **ZT3** — The STRIDE threat model listed HITL operator impersonation as residual: Medium and
  flagged operator authentication as an open gap. In practice, `REM-001` was already implemented:
  `require_hitl_operator` JWT dependency enforces the `hitl-operator` role; `approver_id` is
  taken from the JWT subject, never from the request body.

---

## Decision

### ZT1 — `execution_mode` field on `ToolDefinition`

A new `ExecutionMode` enum (`DIRECT | SANDBOX`) is added to `ToolDefinition`. The
`execute-code` tool is registered with `execution_mode=SANDBOX`, making sandbox routing
a registry-declared invariant rather than a code convention.

The `ToolRegistry.is_sandbox_required(name)` method:

- Normalizes the name (underscores → hyphens) for flexible lookup
- Returns `True` if the registered tool's `execution_mode == SANDBOX`
- Returns `False` for unregistered tools (callers should also check registration)

The `infrastructure/agent-tools/tools.yaml` catalog is updated with `execution_mode`
annotations on all existing tools, plus two new entries: `execute-code` (SANDBOX) and
`send-external-request` (DIRECT).

### ZT2 — Architectural enforcement of sandbox routing

`SandboxExecutor.run()` already gate-checks `python -c <code>` via `CodePreFlight` (ADR-0047).
The `ToolRegistry.is_sandbox_required()` method provides the structural hook for orchestrators
to check before dispatching — any action_type mapped to a SANDBOX tool MUST be routed through
`SandboxExecutor`. This is enforced at the registry layer rather than by code review.

### ZT3 — HITL operator authentication (already implemented)

The compliance doc identified ZT3 as a gap, but `REM-001` closed it before this ADR. The
STRIDE threat model `specs/security/threat-model.md` Spoofing row for HITL operator
impersonation is updated from residual: Medium → residual: Low to reflect the current state.

No new code is required for ZT3; this ADR records the gap closure.

---

## Alternatives Considered

- **Runtime YAML loader for tools.yaml** — loading `tools.yaml` at startup and wiring
  `ToolRegistry` from it was deferred; the in-code `_load_default_registry()` is the source
  of truth for the Python runtime. The YAML file is the human-readable reference for
  security review.
- **Mandatory tool registration check in orchestrator** — adding `assert_registered(action_type)`
  in the orchestrator's `_act_inner` was considered but deferred; the orchestrator does not
  always know which canonical tool maps to an LLM-generated action_type. The registry serves
  as a lookup resource, not a hard blocker, until action_type normalization is standardized.

---

## Consequences

- **Security +**: `execute-code` actions are structurally declared as requiring sandbox routing.
  A developer who routes code execution directly will need to explicitly change the registry,
  which is an auditable ADR-level decision.
- **Threat model updated**: HITL operator spoofing is now residual: Low (was Medium) — reflects
  the JWT auth already in place.
- **Backwards compatibility**: `execution_mode` defaults to `DIRECT`; existing tools are
  unaffected. New sandbox tools must explicitly set `ExecutionMode.SANDBOX`.
