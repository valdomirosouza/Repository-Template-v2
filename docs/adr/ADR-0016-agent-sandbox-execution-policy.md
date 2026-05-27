# ADR-0016 — Agent Sandbox Execution Policy

**Status:** Accepted
**Date:** 2026-05-26
**Authors:** Tech Lead, Security Lead
**Spec:** specs/ai/sandbox-execution.md
**Supersedes:** —
**Superseded by:** —

---

## Context

The multi-agent harness (ADR-0014) allows a GeneratorAgent to produce executable
artifacts — shell commands, SQL, Python scripts — during sprint execution. Running
agent-generated code directly on the host or inside the production container exposes
the system to accidental destructive operations, prompt-injection escapes, and
supply-chain contamination of the codebase.

No sandboxing mechanism was previously defined. The system relied solely on the
HITL Gateway (ADR-0011) for human oversight, but HITL is a decision gate, not an
execution boundary. A human approving an action does not prevent an approved-but-
hallucinated command from having unintended side effects.

Requirements identified:

1. Agent-generated code must run in an isolated environment before integration
2. The isolation must be enforceable regardless of HITL approval status
3. The sandbox policy must be toggleable per environment without code changes
4. The sandbox must not introduce a hard dependency on any cloud provider

---

## Decision

Use **ephemeral Docker containers** as the execution sandbox for agent-generated code,
controlled by a `sandbox-mode` OpenFeature flag.

**Why Docker (not WASM or gVisor):**

- Docker is already in the project stack (docker-compose.yml, CI runners) — zero new
  operational dependency
- `--network none` and `--memory` / `--cpus` flags provide sufficient isolation for
  the current threat model (accidental side effects + prompt injection)
- gVisor (runsc) and WASM runtimes add operational complexity without meaningful
  additional protection for this use case; revisit if the threat model expands

**Key constraints enforced by the sandbox:**

| Constraint                | Docker flag / mechanism                                 |
| ------------------------- | ------------------------------------------------------- |
| No external network       | `--network none`                                        |
| No host filesystem access | Named volume scoped to `sandbox_workdir/` only          |
| No production secrets     | Container receives zero environment variables from host |
| CPU cap                   | `--cpus 1.0`                                            |
| Memory cap                | `--memory 512m`                                         |
| Execution timeout         | `asyncio.wait_for` wrapping `docker run` subprocess     |

**Feature flag (`sandbox-mode`) variants:**

| Variant         | Behaviour                                          | Allowed environments |
| --------------- | -------------------------------------------------- | -------------------- |
| `enabled`       | Sandbox enforced; HITL governs approval separately | all                  |
| `hitl-required` | Sandbox + mandatory HITL before every execution    | all                  |
| `disabled`      | No sandbox; HITL always required as compensation   | `development` only   |

**HITL interaction:**

The sandbox does not replace HITL — it is a complementary layer. An action may be:

- Sandbox-executed without HITL (low risk_score, `sandbox-mode: enabled`)
- Sandbox-executed after HITL approval (high risk_score)
- Blocked entirely (risk_score above absolute ceiling, regardless of sandbox)

---

## Consequences

### Positive

- Eliminates the class of bugs where agent hallucinations cause host-side side effects
- Sandbox results (exit_code, stdout, stderr) feed `EvaluatorAgent` scoring directly,
  improving evaluation accuracy
- `disabled` variant provides a safe escape hatch for local development without
  weakening production controls
- Aligns with EU AI Act Art. 9 (risk management system) and OWASP LLM Top 10 (LLM02,
  LLM04) requirements

### Negative

- Each sandbox execution incurs Docker startup overhead (~200-500 ms for a warm image)
- Requires Docker daemon access from the application process; not suitable for
  environments where Docker-in-Docker is prohibited
- `--network none` blocks any code that needs to call external APIs — intentional by
  design, but must be documented for agent authors

### Neutral

- Container cleanup is `SandboxExecutor`'s responsibility; lingering containers are a
  resource leak and must be tested
- The `sandbox_workdir/` volume is ephemeral — no persistence between sprints

---

## Alternatives Considered

| Alternative                     | Reason rejected                                                               |
| ------------------------------- | ----------------------------------------------------------------------------- |
| subprocess with restricted PATH | Too permeable; no network isolation                                           |
| AWS Firecracker / Lambda        | Cloud dependency; adds cost and IAM complexity                                |
| gVisor (runsc)                  | Requires kernel module; operational overhead unjustified at this threat level |
| WASM (Wasmtime)                 | Language support limited; Python agents cannot run inside WASM today          |
| No sandbox, HITL only           | HITL is a decision gate, not an execution boundary — insufficient alone       |

---

## Implementation Reference

- `src/agents/sandbox_executor.py` — `SandboxExecutor` class and `SandboxResult`
- `docker-compose.sandbox.yml` — isolated sandbox container definition
- `infrastructure/feature-flags/flags/sandbox-mode.yaml` — flag definition
- `tests/unit/agents/test_sandbox_executor.py` — unit test suite
- `specs/ai/sandbox-execution.md` — full specification
