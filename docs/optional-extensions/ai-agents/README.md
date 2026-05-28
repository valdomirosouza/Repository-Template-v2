# AI Agents Module — Optional Extension

> **Status:** Opt-in. This module is **not enabled by default.** Nothing in this directory
> is required for projects that do not use LLMs, autonomous agents, or human-in-the-loop workflows.

---

## What the AI Agents Module includes

| Path                            | Purpose                                                      |
| ------------------------------- | ------------------------------------------------------------ |
| `src/agents/`                   | HITL gateway, orchestrator, harness, risk scorer, sandbox    |
| `src/guardrails/`               | PII filter, prompt injection guard, action limits, audit log |
| `src/memory/`                   | Vector store for agent semantic memory (pgvector)            |
| `specs/ai/`                     | Agent design, HITL/HOTL, guardrails, harness, sandbox specs  |
| `docs/ai-governance/`           | Model card, EU AI Act alignment, NIST AI RMF, bias audit     |
| `infrastructure/feature-flags/` | OpenFeature flags controlling autonomy levels                |

Relevant ADRs (binding only when this module is active):
ADR-0010 · ADR-0011 · ADR-0014 · ADR-0015 · ADR-0016 · ADR-0017

---

## When to enable this module

Enable the AI Agents Module when your project needs **any** of the following:

- LLM-driven request processing (Anthropic Claude or other provider)
- Autonomous agents that take actions on behalf of users
- Human-in-the-Loop (HITL) approval workflows for consequential actions
- Human-on-the-Loop (HOTL) monitoring with autonomous fallback
- Multi-agent harness (Planner → Generator → Evaluator)
- Agent memory / RAG via pgvector

---

## Activation checklist

Complete these steps to activate the AI Agents Module:

- [ ] Set `ANTHROPIC_API_KEY` (or your LLM provider key) in `.env`
- [ ] Set `LLM_PROVIDER` and `LLM_MODEL` in `.env`
- [ ] Set `DB_ENCRYPTION_KEY` to a 64-char hex value (ADR-0018) — never use the placeholder in production
- [ ] Set `REDIS_TLS_ENABLED=true` and use `rediss://` URL in production (ADR-0019)
- [ ] Run `make infra-up` — flagd and pgvector must be running
- [ ] Run `make setup` — applies Alembic migrations including `agent_memory_documents` table
- [ ] Verify `GET /health` and `GET /ready` return `200`
- [ ] Review `docs/ai-governance/` and confirm DPIA/RIPD are current before handling real PII
- [ ] If enabling HOTL autonomous mode: obtain ADR-0015 governance sign-off and set the `autonomous-mode` feature flag

---

## Removal checklist

To remove the AI Agents Module from a project that doesn't need it:

- [ ] Delete `src/agents/`
- [ ] Delete `src/guardrails/`
- [ ] Delete `src/memory/`
- [ ] Delete `specs/ai/`
- [ ] Delete `docs/ai-governance/`
- [ ] Remove the HITL router registration from `src/api/rest/main.py` (search for `hitl`)
- [ ] Remove the `RequestConsumer` lifespan task from `src/api/rest/main.py` (search for `request_consumer`)
- [ ] Remove pgvector from `docker-compose.yml` (the `vector` extension line)
- [ ] Remove Alembic migrations `0002` and `0003` (pgcrypto/vector/agent_memory_documents)
- [ ] Remove `anthropic`, `cryptography` from `pyproject.toml` dependencies if no longer needed
- [ ] Remove `ANTHROPIC_API_KEY`, `LLM_*`, `HITL_*` vars from `.env.example`
- [ ] Remove `infrastructure/feature-flags/` if no other feature flags are needed
- [ ] Delete ADR-0010, ADR-0011, ADR-0014, ADR-0016, ADR-0017 from `docs/adr/` (or keep for historical reference)

---

## Quickstart

See [`docs/quickstart/ai-agents.md`](../../quickstart/ai-agents.md) for a step-by-step guide to configuring HITL, guardrails, harness mode, and autonomous-mode flags.
