# Quickstart — AI Agents Module

> **Prerequisite:** Complete the activation checklist in
> [`docs/optional-extensions/ai-agents/README.md`](../optional-extensions/ai-agents/README.md)
> before following this guide.

---

## 1. Configure your LLM provider

In `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...          # [REQUIRED] from console.anthropic.com
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
LLM_MAX_TOKENS=4096
LLM_CALL_TIMEOUT_SECONDS=30
```

The orchestrator reads `LLM_PROVIDER` at startup and wires the matching client.
To swap providers, implement the `BaseLLMClient` interface and update `LLM_PROVIDER`.

---

## 2. HITL gateway

By default **all** agent actions with real-world effects are blocked until a human approves them.
Pending approvals are stored in Redis (or in-memory for local dev).

**Submit a request:**

```bash
REQUEST_ID=$(curl -s -X POST http://localhost:8000/v1/requests \
  -H "Content-Type: application/json" \
  -d '{"context": {"task": "summarise quarterly report", "source": "internal"}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['request_id'])")
```

**Check its status:**

```bash
curl http://localhost:8000/v1/requests/$REQUEST_ID | python3 -m json.tool
# status: "awaiting_hitl" means the agent proposed an action and is waiting for approval
```

**Approve or reject:**

```bash
# Approve
curl -s -X POST http://localhost:8000/v1/hitl/$HITL_ID/decide \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve", "reviewer": "alice@example.com"}'

# Reject
curl -s -X POST http://localhost:8000/v1/hitl/$HITL_ID/decide \
  -H "Content-Type: application/json" \
  -d '{"decision": "reject", "reviewer": "alice@example.com", "reason": "out of scope"}'
```

HITL timeout behaviour is `reject` — requests never auto-approve (ADR-0011, PRR-AI-005).

---

## 3. Guardrails

Three guardrail layers run automatically in the Perception → Reason → Act pipeline:

| Layer                  | File                                       | When it runs              |
| ---------------------- | ------------------------------------------ | ------------------------- |
| PII Filter             | `src/guardrails/pii_filter.py`             | Before every LLM call     |
| Prompt Injection Guard | `src/guardrails/prompt_injection_guard.py` | Before every LLM call     |
| Action Limits          | `src/guardrails/action_limits.py`          | Before every agent action |
| Audit Logger           | `src/guardrails/audit_logger.py`           | After every agent action  |

Run the security test suite to verify guardrails are intact:

```bash
make test-security-python
```

---

## 4. Harness mode

The `harness_mode` setting controls the agent execution strategy. Set it in `.env`:

| Value        | Behaviour                                                              |
| ------------ | ---------------------------------------------------------------------- |
| `solo`       | Direct to `AgentOrchestrator` — lowest overhead                        |
| `simplified` | Generator + Evaluator loop (no Planner)                                |
| `full`       | Planner → sprint decomposition → Generator + Evaluator with reflection |

```bash
HARNESS_MODE=solo          # default — no harness overhead
```

---

## 5. Agent memory (RAG / pgvector)

Agent memory uses pgvector for semantic search. It is enabled when `src/memory/` is present
and the `agent_memory_documents` table exists (created by Alembic migration `0003`).

```bash
make setup   # runs migrations including 0003
```

To disable memory without removing the module: set `harness_mode=solo` and do not
call `PostgresVectorStore` from your orchestrator.

---

## 6. Autonomous mode (HOTL)

> **Governance gate:** Enabling any autonomy level above `NONE` requires ADR-0015 sign-off.
> **Never** enable `FULL` autonomy in production without explicit governance approval.

Autonomy levels are controlled by feature flags in `infrastructure/feature-flags/`.
The `autonomous-mode` flag file maps to autonomy levels:

```
NONE (default) → all actions require HITL
READ_ONLY      → read-only actions execute without approval
TESTS_ONLY     → test/sandbox actions execute without approval
LOW_RISK       → low-risk actions execute; high-risk still requires HITL
MEDIUM_RISK    → medium + low-risk execute; only high-risk requires HITL
FULL           → all actions execute autonomously (requires ADR-0015 governance approval)
```

To set a level in local dev:

```bash
# Edit infrastructure/feature-flags/autonomous-mode.yaml
# Change defaultVariant to the desired level
make infra-up   # restarts flagd to pick up the change
```

Check current autonomy state:

```bash
make agent-feedback-check   # queries Prometheus for HITL bias metrics
```

---

## 7. Related resources

- `specs/ai/` — full specs for every agent component
- `docs/ai-governance/` — model card, EU AI Act, NIST AI RMF alignment
- `docs/adr/` — ADR-0010 through ADR-0017 (AI Agents Module ADRs)
- `docs/quickstart/hybrid-workflow.md` — Vibe → Agêntico progressive onboarding
