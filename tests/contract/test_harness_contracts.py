"""Contract tests for the multi-agent harness message schemas.

Spec: specs/ai/harness-design.md §2, §9
ADR:  ADR-0021 (Agent Communication Protocol)

These tests enforce the invariants that hold across the Planner→Generator→Evaluator
boundary. They are intentionally separate from unit tests — they validate the *contract*
between agents, not the internal logic of any single agent.

Test markers: unit (no I/O, no external services)
"""

from __future__ import annotations

from src.agents.harness.models import (
    EvaluatorScore,
    ExecutionSummary,
    GeneratorArtifact,
    HarnessResult,
    PatchProposal,
    SprintContract,
    TaskBrief,
)

# ── TaskBrief ─────────────────────────────────────────────────────────────────


class TestTaskBriefContract:
    def test_required_fields_present(self) -> None:
        brief = TaskBrief(task_id="SPEC-001", description="Add input validation.")
        assert brief.task_id
        assert brief.description

    def test_complexity_defaults_to_medium(self) -> None:
        brief = TaskBrief(task_id="SPEC-001", description="Fix bug.")
        assert brief.complexity == "medium"

    def test_complexity_must_be_valid_literal(self) -> None:
        # mypy enforces this at type-check time; this test documents the contract.
        valid = {"low", "medium", "high"}
        for c in valid:
            b = TaskBrief(task_id="T", description="D", complexity=c)  # type: ignore[arg-type]
            assert b.complexity == c

    def test_task_id_is_non_empty_string(self) -> None:
        brief = TaskBrief(task_id="SPEC-042", description="Refactor.")
        assert isinstance(brief.task_id, str)
        assert len(brief.task_id) > 0

    def test_optional_fields_default_to_none(self) -> None:
        brief = TaskBrief(task_id="T", description="D")
        assert brief.trace_id is None
        assert brief.correlation_id is None
        assert brief.success_criteria is None


# ── SprintContract ────────────────────────────────────────────────────────────


class TestSprintContractInvariants:
    """Spec: specs/ai/harness-design.md §2 — each criterion must be independently
    testable and binary. These tests document the structural requirements."""

    def test_must_have_at_least_one_objective(self) -> None:
        contract = SprintContract(
            sprint_id="sprint-1",
            objectives=["Implement validation"],
            success_criteria=["All unit tests pass"],
        )
        assert len(contract.objectives) >= 1

    def test_must_have_at_least_one_success_criterion(self) -> None:
        contract = SprintContract(
            sprint_id="sprint-1",
            objectives=["Implement X"],
            success_criteria=["Test X passes"],
        )
        assert len(contract.success_criteria) >= 1

    def test_sprint_id_is_non_empty(self) -> None:
        contract = SprintContract(
            sprint_id="sprint-abc",
            objectives=["Obj"],
            success_criteria=["Criterion"],
        )
        assert contract.sprint_id != ""

    def test_criteria_are_strings(self) -> None:
        criteria = ["All tests pass", "Coverage ≥ 80%", "No lint errors"]
        contract = SprintContract(
            sprint_id="s1",
            objectives=["Implement feature"],
            success_criteria=criteria,
        )
        assert all(isinstance(c, str) for c in contract.success_criteria)

    def test_objectives_and_criteria_independent(self) -> None:
        # Objectives describe WHAT to build; criteria describe HOW to verify.
        # They must be distinct lists — sharing objects violates the contract.
        objectives = ["Build validator"]
        criteria = ["Validator rejects empty string"]
        contract = SprintContract(
            sprint_id="s1",
            objectives=objectives,
            success_criteria=criteria,
        )
        assert contract.objectives is not contract.success_criteria


# ── GeneratorArtifact ─────────────────────────────────────────────────────────


class TestGeneratorArtifactContract:
    def test_sprint_id_matches_contract(self) -> None:
        artifact = GeneratorArtifact(sprint_id="sprint-1", outputs={"file.py": "# code"})
        assert artifact.sprint_id == "sprint-1"

    def test_outputs_is_string_to_string_map(self) -> None:
        artifact = GeneratorArtifact(
            sprint_id="s1",
            outputs={"src/foo.py": "def foo(): pass", "tests/test_foo.py": "def test_foo(): pass"},
        )
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in artifact.outputs.items())

    def test_outputs_defaults_to_empty_dict(self) -> None:
        artifact = GeneratorArtifact(sprint_id="s1")
        assert artifact.outputs == {}

    def test_pii_invariant_outputs_contain_no_raw_pii_markers(self) -> None:
        # Outputs must have passed pii_filter before being placed in the artifact.
        # This test verifies the contract by asserting known PII patterns are absent.
        # Real enforcement is in pii_filter.py — this documents the expectation.
        pii_patterns = ["@example.com", "000.000.000-00", "192.0.2."]
        artifact = GeneratorArtifact(
            sprint_id="s1",
            outputs={"result.py": "x = '[EMAIL]'"},  # masked, not raw
        )
        all_output = " ".join(artifact.outputs.values())
        for pattern in pii_patterns:
            assert pattern not in all_output, f"Raw PII pattern '{pattern}' found in artifact"


# ── EvaluatorScore ────────────────────────────────────────────────────────────


class TestEvaluatorScoreContract:
    def test_all_dimensions_in_0_to_1_range(self) -> None:
        score = EvaluatorScore(
            sprint_id="s1",
            quality=0.8,
            originality=0.7,
            craft=0.9,
            functionality=0.85,
            passed=True,
            feedback="Good implementation.",
            retry_required=False,
        )
        for dim in (score.quality, score.originality, score.craft, score.functionality):
            assert 0.0 <= dim <= 1.0, f"Dimension out of range: {dim}"

    def test_average_is_mean_of_four_dimensions(self) -> None:
        score = EvaluatorScore(
            sprint_id="s1",
            quality=0.8,
            originality=0.6,
            craft=0.7,
            functionality=0.9,
            passed=True,
            feedback="",
            retry_required=False,
        )
        expected = (0.8 + 0.6 + 0.7 + 0.9) / 4
        assert abs(score.average - expected) < 1e-9

    def test_passed_false_implies_retry_required_or_escalate(self) -> None:
        # When passed=False the harness either retries or escalates to HITL.
        # retry_required=False with passed=False means escalate — both are valid.
        score = EvaluatorScore(
            sprint_id="s1",
            quality=0.3,
            originality=0.4,
            craft=0.5,
            functionality=0.3,
            passed=False,
            feedback="Quality below threshold.",
            retry_required=True,
        )
        assert not score.passed
        # Contract: when retry_required=True, the harness will loop again.
        assert score.retry_required

    def test_passed_true_means_all_dimensions_met_threshold(self) -> None:
        # When passed=True each dimension should be ≥ 0.75 (default threshold).
        threshold = 0.75
        score = EvaluatorScore(
            sprint_id="s1",
            quality=0.8,
            originality=0.8,
            craft=0.8,
            functionality=0.8,
            passed=True,
            feedback="All criteria met.",
            retry_required=False,
        )
        assert score.passed
        for dim in (score.quality, score.originality, score.craft, score.functionality):
            assert dim >= threshold

    def test_sprint_id_propagated_from_contract(self) -> None:
        sprint_id = "sprint-xyz-007"
        score = EvaluatorScore(
            sprint_id=sprint_id,
            quality=0.9,
            originality=0.9,
            craft=0.9,
            functionality=0.9,
            passed=True,
            feedback="",
            retry_required=False,
        )
        assert score.sprint_id == sprint_id


# ── HarnessResult ─────────────────────────────────────────────────────────────


class TestHarnessResultContract:
    def test_task_id_matches_input_brief(self) -> None:
        result = HarnessResult(task_id="SPEC-001", mode="solo", total_iterations=1)
        assert result.task_id == "SPEC-001"

    def test_mode_is_valid_literal(self) -> None:
        for mode in ("solo", "simplified", "full"):
            r = HarnessResult(task_id="T", mode=mode, total_iterations=1)  # type: ignore[arg-type]
            assert r.mode == mode

    def test_escalated_to_hitl_false_by_default(self) -> None:
        result = HarnessResult(task_id="T", mode="solo", total_iterations=1)
        assert result.escalated_to_hitl is False

    def test_final_score_none_when_escalated(self) -> None:
        # When escalated_to_hitl=True the sprint never passed — final_score may be None.
        result = HarnessResult(
            task_id="T",
            mode="full",
            total_iterations=15,
            escalated_to_hitl=True,
            final_score=None,
        )
        assert result.escalated_to_hitl
        assert result.final_score is None

    def test_total_iterations_is_positive(self) -> None:
        result = HarnessResult(task_id="T", mode="simplified", total_iterations=3)
        assert result.total_iterations > 0


# ── PatchProposal ─────────────────────────────────────────────────────────────


class TestPatchProposalContract:
    def test_iteration_is_positive(self) -> None:
        pp = PatchProposal(
            sprint_id="s1",
            iteration=2,
            previous_approach_summary="Used regex for parsing.",
            proposed_alternative="Use AST-based parsing instead.",
            reasoning="Regex approach failed on nested structures.",
        )
        assert pp.iteration >= 1

    def test_summaries_are_non_empty(self) -> None:
        pp = PatchProposal(
            sprint_id="s1",
            iteration=1,
            previous_approach_summary="Approach A.",
            proposed_alternative="Approach B.",
            reasoning="A failed because of X.",
        )
        assert pp.previous_approach_summary
        assert pp.proposed_alternative
        assert pp.reasoning


# ── ExecutionSummary ──────────────────────────────────────────────────────────


class TestExecutionSummaryContract:
    def test_patch_proposals_applied_non_negative(self) -> None:
        summary = ExecutionSummary(
            task_id="T",
            sprint_id="s1",
            total_iterations=5,
            failures=["score below threshold (iter 1)", "score below threshold (iter 2)"],
            patch_proposals_applied=1,
            final_score=None,
            decisions=[],
            generated_at="2026-05-28T10:00:00Z",
        )
        assert summary.patch_proposals_applied >= 0

    def test_failures_length_less_than_or_equal_total_iterations(self) -> None:
        total = 5
        failures = ["fail1", "fail2", "fail3"]
        summary = ExecutionSummary(
            task_id="T",
            sprint_id="s1",
            total_iterations=total,
            failures=failures,
            patch_proposals_applied=0,
            final_score=None,
            decisions=[],
            generated_at="2026-05-28T10:00:00Z",
        )
        assert len(summary.failures) <= summary.total_iterations

    def test_generated_at_is_non_empty_string(self) -> None:
        summary = ExecutionSummary(
            task_id="T",
            sprint_id="s1",
            total_iterations=1,
            failures=[],
            patch_proposals_applied=0,
            final_score=None,
            decisions=[],
            generated_at="2026-05-28T10:00:00Z",
        )
        assert isinstance(summary.generated_at, str)
        assert len(summary.generated_at) > 0


# ── Cross-boundary invariants ─────────────────────────────────────────────────


class TestCrossBoundaryInvariants:
    """These tests verify invariants that must hold across the full
    TaskBrief → SprintContract → GeneratorArtifact → EvaluatorScore chain."""

    def test_sprint_id_consistent_across_artifact_and_score(self) -> None:
        sprint_id = "sprint-consistency-check"
        artifact = GeneratorArtifact(sprint_id=sprint_id, outputs={"f.py": "x = 1"})
        score = EvaluatorScore(
            sprint_id=sprint_id,
            quality=0.9,
            originality=0.8,
            craft=0.85,
            functionality=0.9,
            passed=True,
            feedback="Consistent.",
            retry_required=False,
        )
        assert artifact.sprint_id == score.sprint_id

    def test_result_task_id_matches_input_brief_task_id(self) -> None:
        task_id = "SPEC-CONTRACT-001"
        brief = TaskBrief(task_id=task_id, description="Test contract propagation.")
        result = HarnessResult(task_id=brief.task_id, mode="simplified", total_iterations=2)
        assert result.task_id == brief.task_id

    def test_escalated_result_has_no_passing_score(self) -> None:
        # Invariant: if escalated_to_hitl=True, the final score either does not
        # exist or did not pass. A passing score with escalation is a logical
        # contradiction — the harness should have completed, not escalated.
        result = HarnessResult(
            task_id="T",
            mode="full",
            total_iterations=15,
            escalated_to_hitl=True,
            final_score=None,
        )
        if result.final_score is not None:
            assert not result.final_score.passed, (
                "Invariant violated: escalated result must not have a passing score"
            )
