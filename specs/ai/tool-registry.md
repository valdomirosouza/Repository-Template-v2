# Spec: Governed Tool Registry

**Status:** Approved
**Issue:** #16 | **ADR:** ADR-0039
**Owner:** Security Lead | **Last updated:** 2026-06-05

---

## 1. Purpose

Close Gartner Framework Component gaps T1–T3: formalise tool registration so that
every tool an agent can invoke is declared with its permissions, PII access level,
rate limits, and risk classification before it is reachable at runtime. Unregistered
tool calls are blocked at the orchestrator level.

---

## 2. `ToolDefinition` Schema

| Field                   | Type                   | Required | Description                                    |
| ----------------------- | ---------------------- | -------- | ---------------------------------------------- |
| `name`                  | `str`                  | ✅       | Unique tool identifier (kebab-case)            |
| `description`           | `str`                  | ✅       | Human-readable purpose                         |
| `version`               | `str`                  | ✅       | Semver string; bumped on signature change      |
| `risk_level`            | `low\|medium\|high`    | ✅       | Classification matching HITL thresholds        |
| `pii_access`            | `list[L1\|L2\|L3\|L4]` | ✅       | PII classification levels this tool may access |
| `requires_hitl`         | `bool`                 | ✅       | True if tool must always route through HITL    |
| `rate_limit_per_minute` | `int`                  | ✅       | Max invocations per minute per session         |
| `rate_limit_per_hour`   | `int`                  | ✅       | Max invocations per hour per session           |
| `owner_team`            | `str`                  | ✅       | Team responsible for the tool                  |
| `adr_reference`         | `str`                  | optional | ADR that governs this tool's usage             |
| `endpoint_schema`       | `dict`                 | optional | JSON Schema for the tool's parameters          |

---

## 3. Registry Interface

```python
class ToolRegistry:
    def register(self, tool: ToolDefinition) -> None: ...      # raises ValueError on duplicate name
    def get(self, name: str) -> ToolDefinition: ...            # raises KeyError if not found
    def check_permission(name: str, autonomy_level: AutonomyLevel) -> bool: ...
    def list_by_risk(risk_level: str) -> list[ToolDefinition]: ...
    def all(self) -> list[ToolDefinition]: ...
    def unregister(self, name: str) -> None: ...               # testing only
```

### Permission check logic

| Tool `risk_level` | Tool `requires_hitl` | `AutonomyLevel` | Result                                |
| ----------------- | -------------------- | --------------- | ------------------------------------- |
| any               | True                 | any             | permitted (HITL will gate)            |
| low               | False                | ≥ LOW_RISK      | permitted                             |
| medium            | False                | ≥ MEDIUM_RISK   | permitted                             |
| high              | False                | FULL only       | permitted                             |
| any               | any                  | NONE            | permitted (HITL will gate everything) |

---

## 4. Canonical Tool Catalog

Tools are declared in `infrastructure/agent-tools/tools.yaml`. The registry is
loaded from this file at application startup. Tools must be added there and
re-deployed; runtime `register()` calls are for testing only.

---

## 5. Aggregate Risk Window (Gap T3)

The audit logger tracks tool invocations with `log_tool_invocation()`. An aggregate
risk window check runs after each invocation: if the sum of `risk_score` contributions
from all tool calls in a rolling 5-minute window exceeds `settings.tool_aggregate_risk_threshold`
(default: 3.0), the gateway routes the next action through HITL regardless of individual
tool risk level.

---

## 6. Metrics

| Metric                         | Type    | Labels                               |
| ------------------------------ | ------- | ------------------------------------ |
| `agent_tool_invocations_total` | Counter | `tool_name`, `risk_level`, `outcome` |

---

## 7. Related

- `src/agents/tool_registry.py` — implementation
- `infrastructure/agent-tools/tools.yaml` — canonical tool catalog
- `src/guardrails/audit_logger.py` — `log_tool_invocation()` + aggregate window
- `docs/adr/ADR-0039-governed-tool-registry.md`
