"""OTel span name constants for the agentic observability hierarchy.

Spec: specs/observability/otel-agentic-observability.md §2
ADR:  ADR-0044

Required hierarchy:
  agent.task
    agent.perceive
    agent.reason
      llm.inference
    agent.act
      tool.hitl_gateway
  harness.coordinator
    harness.planner
    harness.evaluator
"""

from opentelemetry import trace

# ── Agent orchestrator spans ──────────────────────────────────────────────────
SPAN_AGENT_TASK = "agent.task"
SPAN_AGENT_PERCEIVE = "agent.perceive"
SPAN_AGENT_REASON = "agent.reason"
SPAN_AGENT_ACT = "agent.act"

# ── LLM execution spans ───────────────────────────────────────────────────────
SPAN_LLM_INFERENCE = "llm.inference"

# ── Tool execution spans ──────────────────────────────────────────────────────
SPAN_TOOL_HITL_GATEWAY = "tool.hitl_gateway"

# ── Harness spans ─────────────────────────────────────────────────────────────
SPAN_HARNESS_COORDINATOR = "harness.coordinator"
SPAN_HARNESS_PLANNER = "harness.planner"
SPAN_HARNESS_EVALUATOR = "harness.evaluator"

# Shared tracer for all agentic instrumentation
tracer = trace.get_tracer("agentic-sdlc", schema_url="https://opentelemetry.io/schemas/1.24.0")
