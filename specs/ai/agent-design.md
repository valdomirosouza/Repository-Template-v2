# Agent Design Spec

**Status:** Approved | **Owner:** AI Lead | **Last updated:** 2026-05-24
**ADR references:** ADR-0010 (Agent Framework), ADR-0011 (HITL/HOTL), ADR-0012 (PII Masking)

---

## Overview

The agent implements a **Perception → Reason → Act** loop with mandatory safety gates at each transition. No autonomous action with real-world effects executes without passing all safety gates.

---

## Loop Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Service                        │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐           │
│  │Perception│──►│  Reason  │──►│   Act    │           │
│  └──────────┘   └──────────┘   └──────────┘           │
│       │               │               │                │
│  PII Filter      Risk Score      Action Limits         │
│  (mandatory)     (mandatory)     (mandatory)           │
│                       │                                │
│               ┌───────▼───────┐                        │
│               │  HITL / HOTL  │                        │
│               │  Gate         │                        │
│               └───────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

---

## Phase Definitions

### Perception

Receives incoming event payload and prepares context for reasoning.

**Required steps (in order):**

1. Deserialise event from Avro schema
2. Apply `pii_filter.mask_dict()` to full payload — **mandatory before any further processing**
3. Retrieve relevant memory from Vector DB (pseudonymised embeddings only)
4. Build agent context object: `{task, masked_context, memory_snippets, trace_id}`
5. Emit `perception.completed` trace span

**Invariants:**

- PII filter runs **before** context is passed to Reason phase
- Raw (unmasked) payload is never stored or forwarded
- Memory retrieval uses pseudonymised queries only

### Reason

Calls LLM provider with masked context and produces a proposed action.

**Required steps (in order):**

1. Construct prompt from masked context only
2. Call LLM provider API (HTTPS, masked context only)
3. Parse LLM response → structured `ProposedAction` object
4. Score action via `RiskScorer.score(action)` → `{score: float, tier: LOW|MEDIUM|HIGH}`
5. Log proposed action to audit logger (masked)
6. Emit `reasoning.completed` trace span with score

**Invariants:**

- LLM call receives **only** masked context — never raw PII
- Every proposed action is scored before routing
- LLM response is never forwarded directly; always parsed to `ProposedAction`

### Act

Executes or routes the proposed action based on risk score.

| Risk tier | Score range | Routing                                         |
| --------- | ----------- | ----------------------------------------------- |
| LOW       | 0.0–0.39    | HOTL — execute with monitoring, notify reviewer |
| MEDIUM    | 0.4–0.69    | HITL — block until human approves or rejects    |
| HIGH      | 0.7–1.0     | HITL — mandatory; auto-reject if timeout        |

**Required steps:**

1. Apply `ActionLimits.check(action)` — enforce per-type rate limits and scope restrictions
2. Route to HITL Gateway (MEDIUM/HIGH) or execute under HOTL monitoring (LOW)
3. After approval or autonomous decision: execute action
4. Publish `agent.action.executed` event to Kafka (masked)
5. Write final audit record (immutable, masked)
6. Emit `action.completed` trace span

**Invariants:**

- `action_limits.py` is always called before execution — no bypass path
- HITL timeout **never** defaults to approval — always rejects
- Every executed action produces an immutable audit record

---

## Agent Configuration

```python
@dataclass
class AgentConfig:
    agent_id: str
    max_actions_per_hour: int = 100
    max_actions_per_day: int = 500
    hitl_timeout_seconds: int = 3600      # 1 hour; expiry = reject
    risk_threshold_hitl: float = 0.4
    risk_threshold_high: float = 0.7
    llm_provider: str = "configured_via_env"
    pii_filter_level: str = "strict"      # strict | permissive
    audit_all_actions: bool = True        # must not be set to False
```

---

## Error Handling

| Failure condition        | Behaviour                                               |
| ------------------------ | ------------------------------------------------------- |
| PII filter error         | Reject request; log error; do NOT fall through unmasked |
| LLM provider timeout     | Return to queue; retry with exponential backoff (3x)    |
| Risk scorer failure      | Default to HIGH tier; route to HITL                     |
| HITL gateway unreachable | Block action; escalate to on-call                       |
| Action execution failure | Write failure record to audit; publish to DLQ           |
| Audit logger failure     | Block action execution; cannot act without audit trail  |

---

## Observability

All agent phases emit OpenTelemetry spans with these attributes:

```
agent.id, agent.phase, event.id, risk.score, risk.tier,
action.type, hitl.required, pii.masked (bool), duration_ms
```

Metrics:

- `agent_actions_total{tier, outcome}` — counter
- `agent_risk_score` — histogram (buckets: 0.1, 0.3, 0.5, 0.7, 0.9, 1.0)
- `agent_hitl_wait_seconds` — histogram
- `agent_pii_filter_duration_ms` — histogram

---

## Implementation Reference

| Component              | File                                       |
| ---------------------- | ------------------------------------------ |
| Agent loop             | `src/agents/agent_loop.py`                 |
| PII filter             | `src/guardrails/pii_filter.py`             |
| Prompt injection guard | `src/guardrails/prompt_injection_guard.py` |
| Risk scorer            | `src/agents/risk_scorer.py`                |
| Action limits          | `src/guardrails/action_limits.py`          |
| HITL gateway           | `src/agents/hitl_gateway.py`               |
| Audit logger           | `src/guardrails/audit_logger.py`           |
