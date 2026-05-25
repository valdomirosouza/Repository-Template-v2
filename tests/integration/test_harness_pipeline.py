"""Integration tests for the multi-agent harness pipeline.

Spec: specs/ai/harness-design.md
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

Tests the end-to-end simplified harness pipeline using StubLLMClient and
InMemoryAuditStorage. No real LLM calls are made. All data is synthetic.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.harness.coordinator import HarnessCoordinator
from src.agents.harness.evaluator import EvaluatorAgent
from src.agents.harness.models import HarnessResult, TaskBrief
from src.agents.harness.planner import PlannerAgent
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
from src.shared.llm_client import StubLLMClient

# ── Synthetic response builders ───────────────────────────────────────────────


def _passing_evaluator_response() -> str:
    return json.dumps(
        {
            "quality": 0.9,
            "originality": 0.85,
            "craft": 0.80,
            "functionality": 0.90,
            "feedback": "All success criteria confirmed.",
            "criteria_results": {},
        }
    )


def _planner_response() -> str:
    return json.dumps(
        {
            "detailed_description": "A synthetic integration test application.",
            "sprint_contracts": [
                {
                    "sprint_id": "sprint-int-001",
                    "objectives": ["User can complete the primary task"],
                    "success_criteria": ["Task completes without error on first attempt"],
                }
            ],
            "ai_feature_opportunities": ["Add AI search capability"],
        }
    )


def _make_brief() -> TaskBrief:
    return TaskBrief(
        task_id="task-int-001",
        description="Build a synthetic integration test task manager",
        complexity="low",
        trace_id="trace-int-001",
    )


# ── Fixture helpers ───────────────────────────────────────────────────────────


def _make_storage() -> tuple[AuditLogger, InMemoryAuditStorage]:
    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)
    return audit, storage


def _make_coordinator(
    audit: AuditLogger,
    generator_response: str = "# synthetic sprint implementation",
) -> HarnessCoordinator:
    evaluator = EvaluatorAgent(
        audit_logger=audit,
        llm_client=StubLLMClient(_passing_evaluator_response()),
    )
    planner = PlannerAgent(
        audit_logger=audit,
        llm_client=StubLLMClient(_planner_response()),
    )

    orchestrator_mock = MagicMock()
    orchestrator_mock.run = AsyncMock(
        return_value={
            "agent_id": "test-orchestrator",
            "action": "summarise",
            "parameters": {},
            "risk_score": 0.1,
            "outcome": "EXECUTED",
            "trace_id": "trace-int-001",
        }
    )

    gateway_mock = MagicMock()
    gateway_mock.submit_for_approval = AsyncMock()

    return HarnessCoordinator(
        audit_logger=audit,
        planner=planner,
        evaluator=evaluator,
        orchestrator=orchestrator_mock,
        hitl_gateway=gateway_mock,
        llm_client=StubLLMClient(generator_response),
    )


# ── Simplified-mode pipeline tests ───────────────────────────────────────────


@pytest.mark.integration
class TestHarnessPipelineSimplified:
    @pytest.mark.asyncio
    async def test_returns_harness_result(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit)

        result = await coordinator.run(_make_brief())

        assert isinstance(result, HarnessResult)

    @pytest.mark.asyncio
    async def test_task_id_preserved_in_result(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit)

        result = await coordinator.run(_make_brief())

        assert result.task_id == "task-int-001"

    @pytest.mark.asyncio
    async def test_mode_field_is_simplified(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit)

        result = await coordinator.run(_make_brief())

        assert result.mode == "simplified"

    @pytest.mark.asyncio
    async def test_artifacts_non_empty(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit)

        result = await coordinator.run(_make_brief())

        assert len(result.artifacts) >= 1

    @pytest.mark.asyncio
    async def test_artifact_sprint_id_is_set(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit)

        result = await coordinator.run(_make_brief())

        for artifact in result.artifacts:
            assert artifact.sprint_id

    @pytest.mark.asyncio
    async def test_final_score_passes_all_dimensions(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit)

        result = await coordinator.run(_make_brief())

        assert result.final_score is not None
        assert result.final_score.passed is True
        assert result.final_score.quality >= 0.75
        assert result.final_score.craft >= 0.75

    @pytest.mark.asyncio
    async def test_no_hitl_escalation_on_first_pass(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit)

        result = await coordinator.run(_make_brief())

        assert result.escalated_to_hitl is False

    @pytest.mark.asyncio
    async def test_audit_events_written_during_pipeline(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, storage = _make_storage()
        coordinator = _make_coordinator(audit)

        await coordinator.run(_make_brief())

        events = await storage.query()
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_evaluator_audit_event_recorded(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, storage = _make_storage()
        coordinator = _make_coordinator(audit)

        await coordinator.run(_make_brief())

        events = await storage.query()
        actions = [e.action for e in events]
        assert "evaluation_completed" in actions

    @pytest.mark.asyncio
    async def test_total_iterations_at_least_one(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit)

        result = await coordinator.run(_make_brief())

        assert result.total_iterations >= 1

    @pytest.mark.asyncio
    async def test_generator_output_stored_in_artifact(self, monkeypatch) -> None:
        monkeypatch.setattr("src.agents.harness.coordinator.settings.harness_mode", "simplified")
        audit, _ = _make_storage()
        coordinator = _make_coordinator(audit, generator_response="# synthetic output for test")

        result = await coordinator.run(_make_brief())

        assert any("synthetic output for test" in str(a.outputs) for a in result.artifacts)
