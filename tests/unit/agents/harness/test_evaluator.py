"""Unit tests for src/agents/harness/evaluator.py.

Spec: specs/ai/harness-design.md §1.3 (EvaluatorAgent)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

All test inputs use clearly synthetic, obviously fake data.
No real personal data appears in this file.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.harness.evaluator import EvaluatorAgent
from src.agents.harness.models import EvaluatorScore, GeneratorArtifact, SprintContract
from src.shared.llm_client import StubLLMClient


def _make_llm_response(
    quality: float = 0.9,
    originality: float = 0.85,
    craft: float = 0.8,
    functionality: float = 0.9,
    feedback: str = "Looks good.",
) -> str:
    return json.dumps(
        {
            "quality": quality,
            "originality": originality,
            "craft": craft,
            "functionality": functionality,
            "feedback": feedback,
            "criteria_results": {},
        }
    )


def _make_contract(criteria: list[str] | None = None) -> SprintContract:
    return SprintContract(
        sprint_id="sprint-test-001",
        objectives=["User can view a dashboard"],
        success_criteria=criteria or ["Dashboard loads within 2 seconds"],
    )


def _make_artifact() -> GeneratorArtifact:
    return GeneratorArtifact(
        sprint_id="sprint-test-001",
        outputs={"src/dashboard.py": "# synthetic implementation"},
    )


def _make_audit_logger() -> MagicMock:
    audit = MagicMock()
    audit.log_event = AsyncMock()
    return audit


class TestEvaluatorPassingScore:
    @pytest.mark.asyncio
    async def test_passed_when_all_dims_above_threshold(self) -> None:
        llm = StubLLMClient(_make_llm_response(0.9, 0.85, 0.8, 0.9))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        assert score.passed is True
        assert score.retry_required is False

    @pytest.mark.asyncio
    async def test_score_fields_populated(self) -> None:
        llm = StubLLMClient(_make_llm_response(0.9, 0.85, 0.8, 0.9))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact(), iteration=3)

        assert score.sprint_id == "sprint-test-001"
        assert score.iteration == 3
        assert score.quality == 0.9
        assert score.craft == 0.8

    @pytest.mark.asyncio
    async def test_average_computed_correctly(self) -> None:
        llm = StubLLMClient(_make_llm_response(1.0, 0.8, 0.6, 0.8))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        assert abs(score.average - 0.8) < 1e-9

    @pytest.mark.asyncio
    async def test_audit_log_called_on_pass(self) -> None:
        audit = _make_audit_logger()
        llm = StubLLMClient(_make_llm_response(0.9, 0.9, 0.9, 0.9))
        evaluator = EvaluatorAgent(audit_logger=audit, llm_client=llm)

        await evaluator.evaluate(_make_contract(), _make_artifact())

        audit.log_event.assert_called_once()
        call_args = audit.log_event.call_args[0][0]
        assert call_args.action == "evaluation_completed"
        assert call_args.metadata["passed"] is True


class TestEvaluatorFailingScore:
    @pytest.mark.asyncio
    async def test_failed_when_one_dim_below_threshold(self) -> None:
        # craft is 0.5, below default threshold of 0.75
        llm = StubLLMClient(_make_llm_response(0.9, 0.85, 0.5, 0.9))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        assert score.passed is False
        assert score.retry_required is True

    @pytest.mark.asyncio
    async def test_failed_when_all_dims_zero(self) -> None:
        llm = StubLLMClient(_make_llm_response(0.0, 0.0, 0.0, 0.0, "Completely broken."))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        assert score.passed is False
        assert score.retry_required is True
        assert "Completely broken" in score.feedback

    @pytest.mark.asyncio
    async def test_audit_log_called_on_fail(self) -> None:
        audit = _make_audit_logger()
        llm = StubLLMClient(_make_llm_response(0.4, 0.4, 0.4, 0.4))
        evaluator = EvaluatorAgent(audit_logger=audit, llm_client=llm)

        await evaluator.evaluate(_make_contract(), _make_artifact())

        audit.log_event.assert_called_once()
        call_args = audit.log_event.call_args[0][0]
        assert call_args.metadata["passed"] is False

    @pytest.mark.asyncio
    async def test_exactly_at_threshold_passes(self) -> None:
        threshold = 0.75
        llm = StubLLMClient(_make_llm_response(threshold, threshold, threshold, threshold))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        assert score.passed is True

    @pytest.mark.asyncio
    async def test_invalid_llm_json_raises_value_error(self) -> None:
        llm = StubLLMClient("not valid json {{{{")
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        with pytest.raises(ValueError, match="invalid JSON"):
            await evaluator.evaluate(_make_contract(), _make_artifact())


class TestEvaluatorReturnsScore:
    @pytest.mark.asyncio
    async def test_returns_evaluator_score_instance(self) -> None:
        llm = StubLLMClient(_make_llm_response())
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        assert isinstance(score, EvaluatorScore)
