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
    groundedness: float | None = None,
) -> str:
    payload: dict[str, object] = {
        "quality": quality,
        "originality": originality,
        "craft": craft,
        "functionality": functionality,
        "feedback": feedback,
        "criteria_results": {},
    }
    if groundedness is not None:
        payload["groundedness"] = groundedness
    return json.dumps(payload)


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


class TestEvaluatorGroundednessSLI:
    """Groundedness SLI wiring (ADR-0080).

    The Evaluator reuses its single LLM call's JSON to emit a SEPARATE
    groundedness metric. It is never an ``EvaluatorScore`` dimension and never
    affects ``passed``. Backward-compatible: a missing/non-numeric field is
    skipped, never fabricated.
    """

    @pytest.mark.asyncio
    async def test_records_groundedness_when_present(self, monkeypatch) -> None:
        calls: list[dict[str, object]] = []

        def _spy(score, flagged, agent_id, sprint_id):  # type: ignore[no-untyped-def]
            calls.append(
                {
                    "score": score,
                    "flagged": flagged,
                    "agent_id": agent_id,
                    "sprint_id": sprint_id,
                }
            )

        monkeypatch.setattr("src.agents.harness.evaluator.record_groundedness", _spy)

        llm = StubLLMClient(_make_llm_response(groundedness=0.95))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        await evaluator.evaluate(_make_contract(), _make_artifact())

        assert len(calls) == 1
        assert calls[0]["score"] == 0.95
        assert calls[0]["flagged"] is False  # 0.95 >= default threshold 0.75
        assert calls[0]["agent_id"] == "evaluator"
        assert calls[0]["sprint_id"] == "sprint-test-001"

    @pytest.mark.asyncio
    async def test_flagged_when_groundedness_below_threshold(self, monkeypatch) -> None:
        calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            "src.agents.harness.evaluator.record_groundedness",
            lambda score, flagged, agent_id, sprint_id: calls.append(
                {"score": score, "flagged": flagged}
            ),
        )

        # Low groundedness (invented behaviour) but all four scored dims pass —
        # proves groundedness is independent of the pass rule.
        llm = StubLLMClient(_make_llm_response(0.9, 0.9, 0.9, 0.9, groundedness=0.3))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        assert len(calls) == 1
        assert calls[0]["score"] == 0.3
        assert calls[0]["flagged"] is True  # 0.3 < threshold 0.75
        # Pass rule untouched: all four dims >= threshold so it still passes.
        assert score.passed is True

    @pytest.mark.asyncio
    async def test_groundedness_in_audit_metadata(self) -> None:
        audit = _make_audit_logger()
        llm = StubLLMClient(_make_llm_response(groundedness=0.8))
        evaluator = EvaluatorAgent(audit_logger=audit, llm_client=llm)

        await evaluator.evaluate(_make_contract(), _make_artifact())

        call_args = audit.log_event.call_args[0][0]
        assert call_args.metadata["groundedness"] == 0.8

    @pytest.mark.asyncio
    async def test_missing_groundedness_field_skips_recording(self, monkeypatch) -> None:
        calls: list[object] = []
        monkeypatch.setattr(
            "src.agents.harness.evaluator.record_groundedness",
            lambda **kw: calls.append(kw),
        )

        # v1-style response: no `groundedness` field at all.
        llm = StubLLMClient(_make_llm_response(0.9, 0.85, 0.8, 0.9))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        # No crash, no recording, EvaluatorScore unchanged.
        assert calls == []
        assert isinstance(score, EvaluatorScore)
        assert score.passed is True
        assert not hasattr(score, "groundedness")

    @pytest.mark.asyncio
    async def test_non_numeric_groundedness_skips_recording(self, monkeypatch) -> None:
        calls: list[object] = []
        monkeypatch.setattr(
            "src.agents.harness.evaluator.record_groundedness",
            lambda **kw: calls.append(kw),
        )

        # Malformed groundedness value — must be ignored, never fabricated.
        raw = json.loads(_make_llm_response(0.9, 0.85, 0.8, 0.9))
        raw["groundedness"] = "high"
        llm = StubLLMClient(json.dumps(raw))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        score = await evaluator.evaluate(_make_contract(), _make_artifact())

        assert calls == []
        assert score.passed is True

    @pytest.mark.asyncio
    async def test_bool_groundedness_skips_recording(self, monkeypatch) -> None:
        calls: list[object] = []
        monkeypatch.setattr(
            "src.agents.harness.evaluator.record_groundedness",
            lambda **kw: calls.append(kw),
        )

        # JSON `true` parses as a Python bool — must NOT be treated as 1.0.
        raw = json.loads(_make_llm_response(0.9, 0.85, 0.8, 0.9))
        raw["groundedness"] = True
        llm = StubLLMClient(json.dumps(raw))
        evaluator = EvaluatorAgent(audit_logger=_make_audit_logger(), llm_client=llm)

        await evaluator.evaluate(_make_contract(), _make_artifact())

        assert calls == []
