# Spec: Agent Sandbox Execution Policy

**ID:** SPEC-sandbox-execution
**Status:** Accepted
**Version:** 1.0.0
**Date:** 2026-05-26
**Authors:** Tech Lead
**ADR:** ADR-0016-agent-sandbox-execution-policy.md
**GitHub Issue:** required before merge

---

## 1. Purpose

Define the mandatory isolation boundary for code generated or proposed by autonomous agents.
No agent-generated code may execute outside a sandboxed environment without explicit HITL
approval. This spec establishes what "sandbox" means, what controls enforce it, and what
exceptions are permitted.

---

## 2. Scope

Applies to:

- `src/agents/orchestrator/orchestrator.py` — when it runs agent-produced code or shell commands
- `src/agents/harness/` — Generator and Evaluator phases that produce or validate artifacts
- Any future agent that produces executable output (scripts, SQL migrations, API calls)

Does NOT apply to:

- Read-only operations (file reads, grep, spec lookups)
- LLM completion calls (governed by `src/agents/hitl_gateway.py` for consequential actions)
- Test runners invoked by the CI pipeline (already isolated by the CI environment)

---

## 3. Threat Model

Agent-generated code may contain:

- Accidental side effects (file writes, network calls) from a confused model
- Prompt-injected payloads designed to escape the agent sandbox
- Destructive operations (DELETE, DROP TABLE, rm -rf) produced by a hallucination

The sandbox must prevent any of these from affecting the host system or production data.

---

## 4. Sandbox Contract

### 4.1 Isolation requirements

| Requirement                                                      | Implementation                                                 |
| ---------------------------------------------------------------- | -------------------------------------------------------------- |
| No access to host filesystem outside a defined working directory | Docker volume mount scoped to `sandbox_workdir/`               |
| No external network access                                       | `--network none` on the sandbox container                      |
| No access to production credentials                              | Sandbox container receives zero secrets; mounts no `.env`      |
| CPU and memory caps                                              | `--cpus 1.0 --memory 512m`                                     |
| Execution timeout                                                | Configurable via `SANDBOX_EXEC_TIMEOUT_SECONDS` (default: 30s) |
| Stdout/stderr capture                                            | All output captured and returned to `SandboxResult`            |

### 4.2 Mandatory HITL escalation

The following conditions MUST escalate to HITL before any sandbox execution:

- `sandbox-mode` feature flag is set to `hitl-required`
- The action's `risk_score >= settings.hitl_risk_threshold`
- The agent requests filesystem writes outside `sandbox_workdir/`
- Any command containing shell metacharacters (`;`, `&&`, `||`, `$()`, backtick) that were
  not explicitly templated by the orchestrator

### 4.3 Execution result contract

`SandboxResult` carries:

- `exit_code: int` — 0 = success
- `stdout: str` — captured output (max 64 KB; truncated with a warning marker)
- `stderr: str` — captured errors (max 16 KB)
- `timed_out: bool`
- `duration_seconds: float`

`SandboxResult` is passed unmodified to `EvaluatorAgent` for scoring.

---

## 5. Feature Flag: `sandbox-mode`

Controlled by `infrastructure/feature-flags/flags/sandbox-mode.yaml`.

| Variant         | Behaviour                                                          |
| --------------- | ------------------------------------------------------------------ |
| `enabled`       | Sandbox required; execution proceeds if flag checks pass           |
| `hitl-required` | Sandbox required AND HITL approval required before every execution |
| `disabled`      | Sandbox bypassed; HITL approval always required as compensation    |

`disabled` is only permitted in local development (`APP_ENV=development`). CI and
production must never run with `sandbox-mode: disabled`.

---

## 6. Out of scope

- WASM or gVisor runtimes — Docker is sufficient for v1; revisit in ADR if threat model expands
- Multi-container sandboxes — single ephemeral container per execution in v1
- Persistent sandbox state across agent sprints — each sprint gets a fresh container

---

## 7. Acceptance criteria

- [ ] `SandboxExecutor.run()` returns `SandboxResult` without raising for any exit code
- [ ] Container is removed after execution (no lingering containers)
- [ ] `--network none` verified in integration test
- [ ] Execution timeout respected within ±1 s
- [ ] `stdout` truncation enforced at 64 KB
- [ ] HITL escalation triggered when `risk_score >= hitl_risk_threshold`
- [ ] Unit test coverage ≥ 80% for `src/agents/sandbox_executor.py`
