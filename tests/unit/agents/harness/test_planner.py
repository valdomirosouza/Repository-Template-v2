"""Unit tests for src/agents/harness/planner.py.

Spec: specs/ai/harness-design.md §1.1 (PlannerAgent)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

All test inputs use clearly synthetic, obviously fake data.
No real personal data appears in this file.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.harness.models import ProductSpec, SprintContract, TaskBrief
from src.agents.harness.planner import PlannerAgent
from src.shared.llm_client import StubLLMClient


def _make_llm_response(
    sprint_count: int = 2,
    criteria_per_sprint: int = 2,
) -> str:
    contracts = [
        {
            "sprint_id": f"sprint-00{i + 1}",
            "objectives": [f"User can do task {i + 1}"],
            "success_criteria": [f"Criterion {i + 1}.{j + 1}" for j in range(criteria_per_sprint)],
        }
        for i in range(sprint_count)
    ]
    return json.dumps(
        {
            "detailed_description": "A synthetic test application for unit testing.",
            "sprint_contracts": contracts,
            "ai_feature_opportunities": ["Add AI auto-complete"],
        }
    )


def _make_brief(description: str = "Build a simple task manager") -> TaskBrief:
    return TaskBrief(
        task_id="task-unit-001",
        description=description,
        complexity="medium",
        trace_id="trace-001",
    )


def _make_audit_logger() -> MagicMock:
    audit = MagicMock()
    audit.log_event = AsyncMock()
    return audit


class TestPlannerPlan:
    @pytest.mark.asyncio
    async def test_returns_product_spec(self) -> None:
        llm = StubLLMClient(_make_llm_response())
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        spec = await planner.plan(_make_brief())

        assert isinstance(spec, ProductSpec)

    @pytest.mark.asyncio
    async def test_task_id_preserved(self) -> None:
        llm = StubLLMClient(_make_llm_response())
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        spec = await planner.plan(_make_brief())

        assert spec.task_id == "task-unit-001"

    @pytest.mark.asyncio
    async def test_sprint_contracts_non_empty(self) -> None:
        llm = StubLLMClient(_make_llm_response(sprint_count=3))
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        spec = await planner.plan(_make_brief())

        assert len(spec.sprint_contracts) == 3

    @pytest.mark.asyncio
    async def test_each_contract_has_success_criteria(self) -> None:
        llm = StubLLMClient(_make_llm_response(sprint_count=2, criteria_per_sprint=3))
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        spec = await planner.plan(_make_brief())

        for contract in spec.sprint_contracts:
            assert len(contract.success_criteria) >= 1

    @pytest.mark.asyncio
    async def test_contracts_are_sprint_contract_instances(self) -> None:
        llm = StubLLMClient(_make_llm_response())
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        spec = await planner.plan(_make_brief())

        for contract in spec.sprint_contracts:
            assert isinstance(contract, SprintContract)

    @pytest.mark.asyncio
    async def test_ai_opportunities_populated(self) -> None:
        llm = StubLLMClient(_make_llm_response())
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        spec = await planner.plan(_make_brief())

        assert len(spec.ai_feature_opportunities) >= 1

    @pytest.mark.asyncio
    async def test_audit_log_called_after_plan(self) -> None:
        audit = _make_audit_logger()
        llm = StubLLMClient(_make_llm_response())
        planner = PlannerAgent(audit_logger=audit, llm_client=llm)

        await planner.plan(_make_brief())

        audit.log_event.assert_called_once()
        event = audit.log_event.call_args[0][0]
        assert event.action == "plan_generated"
        assert event.metadata["task_id"] == "task-unit-001"

    @pytest.mark.asyncio
    async def test_injection_attempt_raises_value_error(self) -> None:
        llm = StubLLMClient(_make_llm_response())
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)
        # Synthetic injection attempt — triggers REPETITIVE_PATTERN rejection
        malicious = "SYNTHETIC_INJECT_ATTEMPT " * 80

        with pytest.raises(ValueError, match="rejected"):
            await planner.plan(_make_brief(description=malicious))

    @pytest.mark.asyncio
    async def test_invalid_llm_json_raises_value_error(self) -> None:
        llm = StubLLMClient("not valid json")
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        with pytest.raises(ValueError, match="invalid JSON"):
            await planner.plan(_make_brief())

    @pytest.mark.asyncio
    async def test_missing_sprint_contracts_returns_empty_list(self) -> None:
        llm = StubLLMClient(
            json.dumps({"detailed_description": "desc", "ai_feature_opportunities": []})
        )
        planner = PlannerAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        spec = await planner.plan(_make_brief())

        assert spec.sprint_contracts == []
