# ADR-0047: Spec Contract Enforcement at Runtime

**Status:** Accepted  
**Date:** 2026-06-06  
**Deciders:** Security Lead, AI Governance Lead  
**Refs:** Issue #32, secure-by-design-agentic-ai-compliance-v2.md §Pillar 1 (SD1, SD2, SD3)

---

## Context

The SDD cycle enforces spec-first development at review time (CLAUDE.md §2), but the
agent's LLM reasoning at runtime is not structurally bound to the spec. Three gaps exist:

- **SD1** — No runtime validation that the proposed action falls within the spec's declared
  `allowed_action_types`. A drifting or injected context could cause the agent to propose
  out-of-scope actions that only the HITL gateway would catch — after the LLM call.
- **SD2** — The Planner → Generator context boundary in `harness_mode=full` is an
  in-memory dict pass. A compromised or hallucinating Planner could inject instructions
  that were not in the original task brief, and the Generator would consume them without
  any integrity check.
- **SD3** — The sandbox executor (ADR-0016) provides runtime isolation via Docker, but
  AI-generated Python code is not statically analysed before it enters the sandbox. A
  `import subprocess; subprocess.run(...)` snippet would fail only at runtime.

---

## Decision

### SD1 — SpecContractEnforcer (`src/agents/spec_contract_enforcer.py`)

- Loads a `SpecContract` (inline dict or YAML sidecar) defining `allowed_action_types`,
  `prohibited_operations`, and `scope_boundary`.
- `inject_contract(system_prompt)` prepends a `[SPEC_CONTRACT]...[/SPEC_CONTRACT]` block
  into the LLM system prompt so the model is aware of its permission boundary before
  generating a proposed action.
- `validate_action(action_type)` is called in `orchestrator._act_inner()` **before** the
  action reaches `HITLGateway` or tool execution. Raises `SpecViolationError` on violation.
- `AgentOrchestrator` accepts an optional `spec_contract_enforcer` parameter; defaults to
  `None` (no enforcement) for backwards compatibility and for agents whose spec does not
  define an action list.

### SD2 — ContextSeal (`src/agents/harness/context_seal.py`)

- `ContextSeal.sign(context_dict)` computes a SHA-256 digest over the JSON-serialized
  context (sorted keys for determinism) and returns a `SealedContext` dataclass.
- `ContextSeal.verify(sealed)` recomputes the digest and raises `ContextTamperingError`
  on mismatch.
- Integrated into `HarnessCoordinator._run_full()`: the `ProductSpec` is sealed
  immediately after `PlannerAgent.plan()` returns; the seal is verified before
  `_execute_sprints()` begins. Verification failure triggers a HITL escalation.

### SD3 — CodePreFlight (`src/agents/code_pre_flight.py`)

- `CodePreFlight.check(code_str)` walks the Python AST and returns a `PreFlightResult`
  with all findings (forbidden imports, forbidden calls).
- Forbidden imports: `subprocess`, `socket`, `ctypes`, `importlib`, `pty`, `pdb`,
  `multiprocessing`, `concurrent.futures`.
- Forbidden calls: `eval`, `exec`, `__import__`, `compile`, `open`.
- `CodePreFlight.check_or_raise(code_str)` raises `CodePreFlightError` on any finding.
- Integrated into `SandboxExecutor.run()`: called when `command[0] == "python"` and
  `command[1] == "-c"` (the primary code-generation path). Raises `SandboxPolicyError`
  to block Docker invocation.

---

## Alternatives Considered

- **Compile-time code signing** — would require signing the generated code at LLM-output
  time, which is impractical given streaming and retry scenarios.
- **Bandit subprocess in CodePreFlight** — more comprehensive but adds a subprocess call
  inside the security gate, which is ironic. AST walking is in-process and sufficient for
  the targeted forbidden patterns.
- **Full HITL on every spec violation** — escalates too aggressively; unknown actions are
  blocked by raising `SpecViolationError` before HITL routing. The calling code may
  choose to escalate or reject.

---

## Consequences

- **Security +**: Three defence-in-depth layers close the SD1/SD2/SD3 gaps. Even if the
  LLM produces an out-of-scope action, the enforcer catches it before tool execution.
- **Backward compatibility**: `SpecContractEnforcer` is optional; existing orchestrator
  usages without a spec contract are unaffected.
- **Test patching**: `SpecContractEnforcer` and `ContextSeal` are pure in-process Python;
  no mocking of external services required in tests.
- **Context seal performance**: SHA-256 over a typical ProductSpec (~2 KB JSON) takes
  < 1 ms. Negligible overhead.
