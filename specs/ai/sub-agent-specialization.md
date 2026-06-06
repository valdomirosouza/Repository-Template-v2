# Spec — Sub-Agent Specialization Registry

**Status:** Approved | **Owner:** Tech Lead | **Last updated:** 2026-06-05
**ADR references:** ADR-0032 (Sub-Agent Specialization Registry), ADR-0014 (Multi-Agent Harness)
**Issue:** #6

---

## 1. Purpose

Define a pluggable registry that allows domain-specific agent specializations to be
registered, retrieved, and filtered — so the harness can dispatch tasks to purpose-built
sub-agents rather than only generic Planner/Generator/Evaluator roles.

---

## 2. AgentConfig Schema

Each registered specialization is described by an `AgentConfig`:

```python
@dataclass
class AgentConfig:
    name: str                        # unique slug, e.g. "security-reviewer"
    role: str                        # human-readable label
    system_prompt_template: str      # Jinja2 template; {{task}} interpolated at dispatch
    tool_set: list[str]              # allowed tool names (subset of available tools)
    risk_level: Literal["low", "medium", "high", "critical"]
    description: str = ""            # optional — shown in operator UI
    max_iterations: int = 3          # max harness retry iterations
    require_hitl: bool = True        # False only for read-only / informational agents
```

### 2.1 Risk Level Semantics

| Level      | Meaning                                   | HITL requirement                |
| ---------- | ----------------------------------------- | ------------------------------- |
| `low`      | Read-only, no external effects            | Optional (HOTL sufficient)      |
| `medium`   | Write to internal systems only            | HITL threshold ≥ 0.5 risk score |
| `high`     | External API calls or data mutations      | HITL always required            |
| `critical` | Financial, legal, or irreversible effects | HITL + dual approval            |

---

## 3. Registry Interface

```python
class SubAgentRegistry:
    def register(name: str, config: AgentConfig) -> None
    def get(name: str) -> AgentConfig            # raises KeyError if not found
    def list_by_risk_level(level: str) -> list[AgentConfig]
    def all() -> list[AgentConfig]
    def unregister(name: str) -> None            # for testing only
```

---

## 4. Built-In Specializations

The registry ships with two reference specializations:

| Name                 | Role                                                            | Risk   | HITL |
| -------------------- | --------------------------------------------------------------- | ------ | ---- |
| `security-reviewer`  | Reviews code diffs for OWASP Top 10 and LLM Top 10 violations   | `high` | Yes  |
| `document-generator` | Generates ADRs, runbooks, and spec drafts from structured input | `low`  | No   |

---

## 5. Observability

Two Prometheus metrics track sub-agent execution:

| Metric                           | Type      | Labels                       | Purpose                                       |
| -------------------------------- | --------- | ---------------------------- | --------------------------------------------- |
| `agent_subtask_duration_seconds` | Histogram | `agent_role`, `harness_mode` | Execution latency per specialization          |
| `agent_subtask_error_total`      | Counter   | `agent_role`, `error_type`   | Error rate per specialization and error class |

---

## 6. Acceptance Criteria

- [ ] `SubAgentRegistry.register()` raises `ValueError` on duplicate name
- [ ] `SubAgentRegistry.get()` raises `KeyError` for unknown name
- [ ] `list_by_risk_level("high")` returns only agents with `risk_level="high"`
- [ ] Built-in specializations (`security-reviewer`, `document-generator`) registered at import
- [ ] Both Prometheus metrics defined in `src/observability/metrics.py`
- [ ] Unit test coverage ≥ 80% in `tests/unit/agents/harness/test_sub_agent_registry.py`
- [ ] ADR-0032 written
