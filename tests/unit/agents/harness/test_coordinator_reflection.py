"""Unit tests for B4 self-reflection features in HarnessCoordinator.

Spec: specs/ai/harness-design.md §9 (Self-Reflection & Auto-Correction)

Tests cover:
  - DecisionTreeLogger integration (decision logged per iteration)
  - PatchProposal generation triggered at threshold
  - PatchProposal injected into subsequent _generate() call
  - ExecutionSummary produced at sprint pass
  - ExecutionSummary produced at HITL escalation, attached to payload
  - harness_patch_proposal_threshold=0 disables PatchProposal
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.harness.coordinator import HarnessCoordinator
from src.agents.harness.models import (
    EvaluatorScore,
    ExecutionSummary,
    PatchProposal,
    SprintContract,
    TaskBrief,
)
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
from src.shared.config import settings

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_score(passed: bool, iteration: int = 1, average: float = 0.4) -> EvaluatorScore:
    dim = average
    return EvaluatorScore(
        sprint_id="sprint-1",
        quality=dim,
        originality=dim,
        craft=dim,
        functionality=dim,
        passed=passed,
        feedback="Synthetic evaluator feedback.",
        retry_required=not passed,
        iteration=iteration,
    )


def _make_contract() -> SprintContract:
    return SprintContract(
        sprint_id="sprint-1",
        objectives=["User can export reports"],
        success_criteria=["Export produces a non-empty CSV file"],
    )


def _make_brief(task_id: str = "task-1") -> TaskBrief:
    return TaskBrief(task_id=task_id, description="Export feature", trace_id="trace-1")


def _make_coordinator(
    audit: AuditLogger,
    evaluator_scores: list[EvaluatorScore],
    patch_response: str | None = None,
) -> HarnessCoordinator:
    """Build a HarnessCoordinator with mocked LLM and evaluator."""
    mock_llm = MagicMock()
    generate_responses = ["synthetic artifact implementation"]
    if patch_response is None:
        patch_response = json.dumps(
            {
                "previous_approach_summary": "Tried approach A.",
                "proposed_alternative": "Try approach B instead.",
                "reasoning": "Approach B avoids the CSV encoding issue.",
            }
        )

    # LLM: first call = generate artifact; subsequent calls may be patch proposals
    mock_llm.complete = AsyncMock(side_effect=[patch_response] * 10 + generate_responses * 10)

    # Separate generate and patch calls via a call counter
    call_count = {"n": 0}
    artifact_response = "synthetic artifact implementation"

    async def llm_complete(system: str, user: str, trace_id: str | None = None) -> str:
        call_count["n"] += 1
        if "self-reflection" in system.lower():
            return patch_response
        return artifact_response

    mock_llm.complete = AsyncMock(side_effect=llm_complete)

    mock_evaluator = MagicMock()
    score_iter = iter(evaluator_scores)
    mock_evaluator.evaluate = AsyncMock(side_effect=lambda *a, **kw: next(score_iter))

    mock_hitl = MagicMock()
    mock_hitl.submit_for_approval = AsyncMock()
    mock_orchestrator = MagicMock()
    mock_planner = MagicMock()

    return HarnessCoordinator(
        audit_logger=audit,
        planner=mock_planner,
        evaluator=mock_evaluator,
        orchestrator=mock_orchestrator,
        hitl_gateway=mock_hitl,
        llm_client=mock_llm,
    )


@pytest.fixture()
def storage() -> InMemoryAuditStorage:
    return InMemoryAuditStorage()


@pytest.fixture()
def audit(storage: InMemoryAuditStorage) -> AuditLogger:
    return AuditLogger(storage)


# ── decision tree logging ─────────────────────────────────────────────────────


class TestDecisionLoggingPerIteration:
    @pytest.mark.asyncio
    async def test_first_iteration_logs_fresh_generation(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        coordinator = _make_coordinator(audit, [_make_score(passed=True)])
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_mode", "simplified"),
            patch.object(settings, "harness_evaluator_enabled", True),
            patch.object(settings, "harness_patch_proposal_threshold", 2),
        ):
            await coordinator._run_sprint(brief, contract)

        decisions = await storage.query(action_type="decision_bifurcation")
        assert len(decisions) >= 1
        first = decisions[0]
        assert first.metadata["option_chosen"] == "fresh_generation"
        assert "First attempt" in first.metadata["rationale"]

    @pytest.mark.asyncio
    async def test_second_iteration_logs_feedback_incorporation(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        scores = [_make_score(passed=False, iteration=1), _make_score(passed=True, iteration=2)]
        coordinator = _make_coordinator(audit, scores)
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_mode", "simplified"),
            patch.object(settings, "harness_evaluator_enabled", True),
            patch.object(settings, "harness_patch_proposal_threshold", 2),
        ):
            await coordinator._run_sprint(brief, contract)

        decisions = await storage.query(action_type="decision_bifurcation")
        # iteration 1 = fresh_generation, iteration 2 = feedback_incorporation
        chosen_options = [d.metadata["option_chosen"] for d in decisions]
        assert "fresh_generation" in chosen_options
        assert "feedback_incorporation" in chosen_options

    @pytest.mark.asyncio
    async def test_decision_count_matches_iterations(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        # 3 iterations: fail, fail, pass
        scores = [
            _make_score(passed=False, iteration=1),
            _make_score(passed=False, iteration=2),
            _make_score(passed=True, iteration=3),
        ]
        coordinator = _make_coordinator(audit, scores)
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_mode", "simplified"),
            patch.object(settings, "harness_evaluator_enabled", True),
            patch.object(settings, "harness_patch_proposal_threshold", 5),
        ):
            await coordinator._run_sprint(brief, contract)

        decisions = await storage.query(action_type="decision_bifurcation")
        assert len(decisions) == 3


# ── patch proposal threshold ──────────────────────────────────────────────────


class TestPatchProposalThreshold:
    @pytest.mark.asyncio
    async def test_patch_proposal_logged_at_threshold(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        # threshold=2 → PatchProposal triggered on iteration 3 (after 2 failures)
        scores = [
            _make_score(passed=False, iteration=1),
            _make_score(passed=False, iteration=2),
            _make_score(passed=True, iteration=3),
        ]
        coordinator = _make_coordinator(audit, scores)
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_patch_proposal_threshold", 2),
            patch.object(settings, "harness_evaluator_enabled", True),
        ):
            await coordinator._run_sprint(brief, contract)

        decisions = await storage.query(action_type="decision_bifurcation")
        patch_decisions = [
            d for d in decisions if d.metadata["option_chosen"] == "generate_patch_proposal"
        ]
        assert len(patch_decisions) == 1

    @pytest.mark.asyncio
    async def test_no_patch_proposal_when_threshold_is_zero(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        scores = [
            _make_score(passed=False, iteration=1),
            _make_score(passed=True, iteration=2),
        ]
        coordinator = _make_coordinator(audit, scores)
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_patch_proposal_threshold", 0),
            patch.object(settings, "harness_evaluator_enabled", True),
        ):
            await coordinator._run_sprint(brief, contract)

        decisions = await storage.query(action_type="decision_bifurcation")
        patch_decisions = [
            d for d in decisions if d.metadata["option_chosen"] == "generate_patch_proposal"
        ]
        assert len(patch_decisions) == 0

    @pytest.mark.asyncio
    async def test_no_patch_proposal_below_threshold(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        # threshold=3: only 1 failure before passing → no PatchProposal
        scores = [
            _make_score(passed=False, iteration=1),
            _make_score(passed=True, iteration=2),
        ]
        coordinator = _make_coordinator(audit, scores)
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_patch_proposal_threshold", 3),
            patch.object(settings, "harness_evaluator_enabled", True),
        ):
            await coordinator._run_sprint(brief, contract)

        decisions = await storage.query(action_type="decision_bifurcation")
        patch_decisions = [
            d for d in decisions if d.metadata["option_chosen"] == "generate_patch_proposal"
        ]
        assert len(patch_decisions) == 0


# ── _generate_patch_proposal ──────────────────────────────────────────────────


class TestGeneratePatchProposal:
    @pytest.mark.asyncio
    async def test_returns_patch_proposal_with_valid_json(self, audit: AuditLogger) -> None:
        coordinator = _make_coordinator(audit, [])
        contract = _make_contract()
        score = _make_score(passed=False, iteration=2)

        result = await coordinator._generate_patch_proposal(contract, score, iteration=3)

        assert isinstance(result, PatchProposal)
        assert result.sprint_id == "sprint-1"
        assert result.iteration == 3
        assert len(result.proposed_alternative) > 0

    @pytest.mark.asyncio
    async def test_falls_back_on_invalid_json_response(self, audit: AuditLogger) -> None:
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="not valid json {{{{")

        coordinator = HarnessCoordinator(
            audit_logger=audit,
            planner=MagicMock(),
            evaluator=MagicMock(),
            orchestrator=MagicMock(),
            hitl_gateway=MagicMock(),
            llm_client=mock_llm,
        )
        contract = _make_contract()
        score = _make_score(passed=False, iteration=2)

        result = await coordinator._generate_patch_proposal(contract, score, iteration=3)

        assert isinstance(result, PatchProposal)
        assert "fallback" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_patch_proposal_sprint_id_matches_contract(self, audit: AuditLogger) -> None:
        coordinator = _make_coordinator(audit, [])
        contract = _make_contract()
        score = _make_score(passed=False, iteration=2)

        result = await coordinator._generate_patch_proposal(contract, score, iteration=3)

        assert result.sprint_id == contract.sprint_id


# ── execution summary ─────────────────────────────────────────────────────────


class TestExecutionSummary:
    @pytest.mark.asyncio
    async def test_execution_summary_logged_on_sprint_pass(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        coordinator = _make_coordinator(audit, [_make_score(passed=True)])
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_evaluator_enabled", True),
            patch.object(settings, "harness_patch_proposal_threshold", 2),
        ):
            await coordinator._run_sprint(brief, contract)

        summaries = await storage.query(action_type="sprint_execution_summary")
        assert len(summaries) == 1
        s = summaries[0]
        assert s.metadata["task_id"] == "task-1"
        assert s.metadata["sprint_id"] == "sprint-1"
        assert s.metadata["final_passed"] is True

    @pytest.mark.asyncio
    async def test_execution_summary_logged_on_hitl_escalation(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        failing_scores = [_make_score(passed=False, iteration=i) for i in range(1, 4)]
        coordinator = _make_coordinator(audit, failing_scores)
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_max_iterations", 3),
            patch.object(settings, "harness_evaluator_enabled", True),
            patch.object(settings, "harness_patch_proposal_threshold", 2),
        ):
            await coordinator._run_sprint(brief, contract)

        summaries = await storage.query(action_type="sprint_execution_summary")
        assert len(summaries) == 1
        s = summaries[0]
        assert s.metadata["failures_count"] == 3
        assert s.metadata["final_passed"] is False

    @pytest.mark.asyncio
    async def test_execution_summary_contains_decision_count(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        scores = [
            _make_score(passed=False, iteration=1),
            _make_score(passed=True, iteration=2),
        ]
        coordinator = _make_coordinator(audit, scores)
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_evaluator_enabled", True),
            patch.object(settings, "harness_patch_proposal_threshold", 5),
        ):
            await coordinator._run_sprint(brief, contract)

        summaries = await storage.query(action_type="sprint_execution_summary")
        assert summaries[0].metadata["decision_count"] == 2

    @pytest.mark.asyncio
    async def test_execution_summary_patch_proposals_counted(
        self, audit: AuditLogger, storage: InMemoryAuditStorage
    ) -> None:
        scores = [
            _make_score(passed=False, iteration=1),
            _make_score(passed=False, iteration=2),
            _make_score(passed=True, iteration=3),
        ]
        coordinator = _make_coordinator(audit, scores)
        brief, contract = _make_brief(), _make_contract()

        with (
            patch.object(settings, "harness_patch_proposal_threshold", 2),
            patch.object(settings, "harness_evaluator_enabled", True),
        ):
            await coordinator._run_sprint(brief, contract)

        summaries = await storage.query(action_type="sprint_execution_summary")
        assert summaries[0].metadata["patch_proposals_applied"] == 1


# ── execution summary attached to HITL escalation payload ────────────────────


class TestExecutionSummaryInHITLPayload:
    @pytest.mark.asyncio
    async def test_hitl_payload_includes_execution_summary(self, audit: AuditLogger) -> None:
        failing_scores = [_make_score(passed=False, iteration=i) for i in range(1, 4)]
        coordinator = _make_coordinator(audit, failing_scores)
        brief, contract = _make_brief(), _make_contract()

        captured_payload: dict = {}

        async def capture_hitl(request):
            captured_payload.update(request.action_parameters)

        coordinator._hitl.submit_for_approval = AsyncMock(side_effect=capture_hitl)

        with (
            patch.object(settings, "harness_max_iterations", 3),
            patch.object(settings, "harness_evaluator_enabled", True),
            patch.object(settings, "harness_patch_proposal_threshold", 2),
        ):
            await coordinator._run_sprint(brief, contract)

        assert "execution_summary" in captured_payload
        es = captured_payload["execution_summary"]
        assert es["total_iterations"] == 3
        assert es["failures_count"] == 3

    @pytest.mark.asyncio
    async def test_hitl_payload_execution_summary_failures_capped_at_10(
        self, audit: AuditLogger
    ) -> None:
        # Build 12 failing scores; failures list in payload must be capped at 10
        failing_scores = [_make_score(passed=False, iteration=i) for i in range(1, 13)]
        coordinator = _make_coordinator(audit, failing_scores)
        brief, contract = _make_brief(), _make_contract()

        captured_payload: dict = {}

        async def capture_hitl(request):
            captured_payload.update(request.action_parameters)

        coordinator._hitl.submit_for_approval = AsyncMock(side_effect=capture_hitl)

        with (
            patch.object(settings, "harness_max_iterations", 12),
            patch.object(settings, "harness_evaluator_enabled", True),
            patch.object(settings, "harness_patch_proposal_threshold", 2),
        ):
            await coordinator._run_sprint(brief, contract)

        failures_in_payload = captured_payload["execution_summary"]["failures"]
        assert len(failures_in_payload) <= 10


# ── _build_execution_summary ──────────────────────────────────────────────────


class TestBuildExecutionSummary:
    def test_all_fields_populated(self, audit: AuditLogger) -> None:
        from src.agents.harness.decision_tree_logger import DecisionTreeLogger

        coordinator = _make_coordinator(audit, [])
        brief, contract = _make_brief(), _make_contract()
        dt_logger = DecisionTreeLogger(audit, "harness.coordinator", brief.task_id)
        score = _make_score(passed=True)

        summary = coordinator._build_execution_summary(
            brief=brief,
            contract=contract,
            total_iterations=2,
            failures=["iteration_1: score=0.40 feedback=..."],
            patch_proposals_applied=1,
            final_score=score,
            dt_logger=dt_logger,
        )

        assert isinstance(summary, ExecutionSummary)
        assert summary.task_id == "task-1"
        assert summary.sprint_id == "sprint-1"
        assert summary.total_iterations == 2
        assert len(summary.failures) == 1
        assert summary.patch_proposals_applied == 1
        assert summary.final_score is score
        assert summary.decisions == []
        assert summary.generated_at  # non-empty ISO8601

    def test_failures_list_is_a_copy(self, audit: AuditLogger) -> None:
        from src.agents.harness.decision_tree_logger import DecisionTreeLogger

        coordinator = _make_coordinator(audit, [])
        brief, contract = _make_brief(), _make_contract()
        dt_logger = DecisionTreeLogger(audit, "harness.coordinator", brief.task_id)
        failures = ["f1", "f2"]

        summary = coordinator._build_execution_summary(
            brief, contract, 2, failures, 0, None, dt_logger
        )

        failures.append("f3")
        assert len(summary.failures) == 2  # summary was not mutated
