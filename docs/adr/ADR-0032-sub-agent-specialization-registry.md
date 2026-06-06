# ADR-0032: Sub-Agent Specialization Registry

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Spec:** `specs/ai/sub-agent-specialization.md`
**Issue:** #6
**Related ADRs:** ADR-0014 (Multi-Agent Harness), ADR-0011 (HITL/HOTL), ADR-0034 (Escalation Protocol)

---

## Context

The current harness (`src/agents/harness/`) defines three generic roles —
Planner, Generator, and Evaluator — that apply uniformly to every task.
The _2026 Agentic Coding Trends Report_ identifies "specialised sub-agents"
as a key driver of multi-agent productivity: domain-specific agents with
tailored system prompts, restricted tool sets, and appropriate risk levels
outperform generic agents on their target domains (Gap 2.1).

Two additional gaps drove this decision:

- **Gap 2.2** — No mechanism for parallel context window isolation.
  A registry is the prerequisite: you cannot dispatch to a specialised agent
  in a separate context window without knowing that agent's config at dispatch time.
- **Gap 2.3** — Prometheus metrics aggregate all agent behaviour.
  Per-sub-agent breakdown metrics require a stable identity (`agent_role`) that
  only a registry can provide.

---

## Decision

Introduce `SubAgentRegistry` in `src/agents/harness/sub_agent_registry.py`:

- **`AgentConfig`** dataclass: `name`, `role`, `system_prompt_template` (Jinja2),
  `tool_set`, `risk_level` (`low|medium|high|critical`), `description`,
  `max_iterations`, `require_hitl`.
- **`SubAgentRegistry`** class: `register`, `get`, `list_by_risk_level`, `all`, `unregister`.
  Populated at startup; read-only at runtime.
- **Module-level singleton** `default_registry` pre-populated with two reference
  specializations: `security-reviewer` (high risk, HITL required) and
  `document-generator` (low risk, HOTL sufficient).
- **Two new Prometheus metrics** in `src/observability/metrics.py`:
  - `agent_subtask_duration_seconds{agent_role, harness_mode}` (histogram)
  - `agent_subtask_error_total{agent_role, error_type}` (counter)

Risk level semantics are binding: `high` and `critical` agents always route through
the HITL gateway regardless of the global autonomy feature flag.

---

## Consequences

**Positive:**

- Domain-specific agents can be added without modifying core harness logic —
  register a new `AgentConfig` and the harness can dispatch to it.
- `agent_role` label on Prometheus metrics makes per-specialization performance
  visible in Grafana without any dashboard schema change.
- `require_hitl=False` is only permitted for `low` risk agents, enforced by the
  registry's risk-level semantics — no HITL bypass is possible for `medium`+ agents.

**Neutral:**

- The registry is populated at startup, not at runtime. Dynamic registration
  (adding a specialization without restarting) is out of scope for this ADR.
- `system_prompt_template` is a plain string with `{{task}}` interpolation.
  A full Jinja2 environment is not introduced; only the `{{task}}` placeholder
  is supported in this version.

**Risk:**

- A misconfigured `tool_set` could grant a specialization access to tools beyond
  its intended scope. Mitigated by: (a) tool_set is checked at dispatch before
  execution; (b) new specializations require a dual-use assessment (ADR-0034).
