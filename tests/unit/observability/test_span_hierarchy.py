"""Unit tests for orchestrator + harness OTel span hierarchy.

Spec: specs/observability/otel-agentic-observability.md §2–§3
ADR:  ADR-0044
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.observability.span_hierarchy import (
    SPAN_AGENT_ACT,
    SPAN_AGENT_PERCEIVE,
    SPAN_AGENT_REASON,
    SPAN_AGENT_TASK,
    SPAN_HARNESS_COORDINATOR,
    SPAN_HARNESS_EVALUATOR,
    SPAN_HARNESS_PLANNER,
)


def _make_tracer_with_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _span_names(exporter: InMemorySpanExporter) -> list[str]:
    return [span.name for span in exporter.get_finished_spans()]


def _find_span(exporter: InMemorySpanExporter, name: str):
    return next((s for s in exporter.get_finished_spans() if s.name == name), None)


# ── Span name constants ───────────────────────────────────────────────────────


class TestSpanNameConstants:
    def test_agent_task_name(self) -> None:
        assert SPAN_AGENT_TASK == "agent.task"

    def test_agent_perceive_name(self) -> None:
        assert SPAN_AGENT_PERCEIVE == "agent.perceive"

    def test_agent_reason_name(self) -> None:
        assert SPAN_AGENT_REASON == "agent.reason"

    def test_agent_act_name(self) -> None:
        assert SPAN_AGENT_ACT == "agent.act"

    def test_harness_coordinator_name(self) -> None:
        assert SPAN_HARNESS_COORDINATOR == "harness.coordinator"

    def test_harness_planner_name(self) -> None:
        assert SPAN_HARNESS_PLANNER == "harness.planner"

    def test_harness_evaluator_name(self) -> None:
        assert SPAN_HARNESS_EVALUATOR == "harness.evaluator"


# ── Orchestrator span hierarchy ───────────────────────────────────────────────


class TestOrchestratorSpanHierarchy:
    """Patches tracer at the import site in orchestrator.py (not in span_hierarchy.py)
    because the orchestrator imports `tracer` directly via `from ... import tracer`."""

    @pytest.fixture()
    def otel_setup(self):
        provider, exporter = _make_tracer_with_exporter()
        test_tracer = provider.get_tracer("test")
        with patch("src.agents.orchestrator.orchestrator.tracer", test_tracer):
            yield exporter
        exporter.clear()

    @pytest.mark.asyncio
    async def test_run_emits_agent_task_span(self, otel_setup: InMemorySpanExporter) -> None:
        orch = _make_orchestrator()
        await orch.run(raw_input={"action_type": "read_file", "path": "/tmp/x"}, trace_id="t-1")
        assert SPAN_AGENT_TASK in _span_names(otel_setup)

    @pytest.mark.asyncio
    async def test_run_emits_perceive_span(self, otel_setup: InMemorySpanExporter) -> None:
        orch = _make_orchestrator()
        await orch.run(raw_input={"action_type": "read_file"}, trace_id="t-2")
        assert SPAN_AGENT_PERCEIVE in _span_names(otel_setup)

    @pytest.mark.asyncio
    async def test_run_emits_reason_span(self, otel_setup: InMemorySpanExporter) -> None:
        orch = _make_orchestrator()
        await orch.run(raw_input={"action_type": "read_file"}, trace_id="t-3")
        assert SPAN_AGENT_REASON in _span_names(otel_setup)

    @pytest.mark.asyncio
    async def test_run_emits_act_span(self, otel_setup: InMemorySpanExporter) -> None:
        orch = _make_orchestrator()
        await orch.run(raw_input={"action_type": "read_file"}, trace_id="t-4")
        assert SPAN_AGENT_ACT in _span_names(otel_setup)

    @pytest.mark.asyncio
    async def test_agent_task_carries_agent_id_attribute(
        self, otel_setup: InMemorySpanExporter
    ) -> None:
        orch = _make_orchestrator(agent_id="test-agent")
        await orch.run(raw_input={"action_type": "read_file"}, trace_id="t-5")
        span = _find_span(otel_setup, SPAN_AGENT_TASK)
        assert span is not None
        assert span.attributes.get("agent.id") == "test-agent"

    @pytest.mark.asyncio
    async def test_act_span_carries_risk_score_attribute(
        self, otel_setup: InMemorySpanExporter
    ) -> None:
        orch = _make_orchestrator()
        await orch.run(raw_input={"action_type": "read_file"}, trace_id="t-6")
        span = _find_span(otel_setup, SPAN_AGENT_ACT)
        assert span is not None
        assert "act.risk_score" in span.attributes

    @pytest.mark.asyncio
    async def test_perceive_span_carries_pii_fields_masked_attribute(
        self, otel_setup: InMemorySpanExporter
    ) -> None:
        orch = _make_orchestrator()
        await orch.run(raw_input={"action_type": "read_file"}, trace_id="t-7")
        span = _find_span(otel_setup, SPAN_AGENT_PERCEIVE)
        assert span is not None
        assert "perceive.pii_fields_masked" in span.attributes


# ── Harness coordinator span hierarchy ───────────────────────────────────────


class TestHarnessCoordinatorSpanHierarchy:
    """Patches tracer at the import site in coordinator.py."""

    @pytest.mark.asyncio
    async def test_coordinator_run_emits_harness_coordinator_span(self) -> None:
        from src.agents.harness.models import TaskBrief

        provider, exporter = _make_tracer_with_exporter()
        with patch("src.agents.harness.coordinator.tracer", provider.get_tracer("test")):
            coordinator = _make_coordinator()
            brief = TaskBrief(task_id="task-1", description="Test task")
            await coordinator.run(brief)

        assert SPAN_HARNESS_COORDINATOR in _span_names(exporter)

    @pytest.mark.asyncio
    async def test_harness_coordinator_span_has_stage_attribute(self) -> None:
        from src.agents.harness.models import TaskBrief

        provider, exporter = _make_tracer_with_exporter()
        with patch("src.agents.harness.coordinator.tracer", provider.get_tracer("test")):
            coordinator = _make_coordinator()
            brief = TaskBrief(task_id="task-2", description="Test task")
            await coordinator.run(brief)

        span = _find_span(exporter, SPAN_HARNESS_COORDINATOR)
        assert span is not None
        assert span.attributes.get("harness.stage") == "coordinator"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_orchestrator(agent_id: str = "test-agent") -> Any:
    from src.agents.orchestrator.orchestrator import AgentOrchestrator

    llm = AsyncMock()
    # Use a registered starter-catalog tool so the action survives ToolExecutor
    # registry enforcement (ADR-0048/0053) and the full span hierarchy is emitted.
    llm.complete = AsyncMock(
        return_value='{"action": "read-db-record", "parameters": {}, "risk_score": 0.1}'
    )
    audit = AsyncMock()
    audit.log_event = AsyncMock()
    hitl = AsyncMock()
    hitl.submit_for_approval = AsyncMock()

    from src.agents.hitl_gateway import HITLStatus

    approved = MagicMock()
    approved.status = HITLStatus.APPROVED
    hitl.submit_for_approval.return_value = approved

    return AgentOrchestrator(
        agent_id=agent_id,
        audit_logger=audit,
        hitl_gateway=hitl,
        llm_client=llm,
    )


def _make_coordinator() -> Any:
    from src.agents.harness.coordinator import HarnessCoordinator

    orchestrator = AsyncMock()
    orchestrator.run = AsyncMock(
        return_value={"action": "read_file", "outcome": "EXECUTED", "risk_score": 0.1}
    )
    audit = AsyncMock()
    audit.log_event = AsyncMock()
    planner = AsyncMock()
    evaluator = AsyncMock()
    hitl = AsyncMock()
    llm = AsyncMock()

    coordinator = HarnessCoordinator(
        audit_logger=audit,
        planner=planner,
        evaluator=evaluator,
        orchestrator=orchestrator,
        hitl_gateway=hitl,
        llm_client=llm,
    )
    return coordinator
