"""Model contract — groundedness as an SLI (ADR-0080).

Validates the harness evaluator's *groundedness* dimension: every factual or
API-level claim in the generated artifact (and in the evaluator's own feedback)
must trace to a provided source (the sprint contract, the artifacts, or the
success criteria). Confidently-stated unsupported claims are flagged; hedged or
explicitly-uncertain statements are acceptable.

Two layers, mirroring the rest of this suite:

  * Recorded-stub layer (default, NO API key required): drives the real
    `EvaluatorAgent` parsing/gating path with recorded LLM JSON responses, so the
    grounding contract is asserted deterministically on every CI run.
  * Live layer (`@pytest.mark.model_contract`): runs the real model and is
    auto-skipped by conftest when ANTHROPIC_API_KEY is absent. It guards against
    behavioural drift when a new model version is promoted.

All data here is synthetic. No real personal data appears in this file.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.harness.evaluator import EvaluatorAgent
from src.agents.harness.models import GeneratorArtifact, SprintContract
from src.shared.llm_client import StubLLMClient

# ── Helpers ──────────────────────────────────────────────────────────────────


def _recorded_response(
    *,
    groundedness: float,
    unsupported_claims: list[str] | None = None,
    quality: float = 0.9,
    originality: float = 0.85,
    craft: float = 0.85,
    functionality: float = 0.9,
    feedback: str = "Recorded evaluation.",
) -> str:
    """A recorded evaluator JSON response (as the v2 prompt instructs)."""
    return json.dumps(
        {
            "quality": quality,
            "originality": originality,
            "craft": craft,
            "functionality": functionality,
            "groundedness": groundedness,
            "feedback": feedback,
            "unsupported_claims": unsupported_claims or [],
            "criteria_results": {},
        }
    )


def _contract() -> SprintContract:
    return SprintContract(
        sprint_id="sprint-grounded-001",
        objectives=["User can export a report as CSV"],
        success_criteria=["Export endpoint returns a CSV with the documented columns"],
    )


def _artifact() -> GeneratorArtifact:
    return GeneratorArtifact(
        sprint_id="sprint-grounded-001",
        outputs={"src/export.py": "# synthetic implementation"},
    )


def _make_evaluator(recorded: str) -> EvaluatorAgent:
    audit = MagicMock()
    audit.log_event = AsyncMock()
    return EvaluatorAgent(audit_logger=audit, llm_client=StubLLMClient(recorded))


# ── Recorded-stub layer (no API key) ─────────────────────────────────────────


class TestGroundednessContract:
    """The evaluator must expose and gate groundedness, and surface unsupported
    claims — all without a live model."""

    async def test_fully_grounded_response_passes(self) -> None:
        evaluator = _make_evaluator(_recorded_response(groundedness=1.0))

        score = await evaluator.evaluate(_contract(), _artifact())

        assert score.groundedness == 1.0
        assert score.unsupported_claims == []
        assert score.passed is True

    async def test_unsupported_claim_below_threshold_fails(self) -> None:
        # A fabricated API claim → low groundedness → must FAIL and retry.
        evaluator = _make_evaluator(
            _recorded_response(
                groundedness=0.4,
                unsupported_claims=[
                    "Calls report.to_parquet() — no such method in the provided sources",
                ],
            )
        )

        score = await evaluator.evaluate(_contract(), _artifact())

        assert score.groundedness < 0.75
        assert score.passed is False
        assert score.retry_required is True
        assert score.unsupported_claims, "unsupported claims must be surfaced for the retry loop"

    async def test_grounding_ratio_measured_per_evaluation(self) -> None:
        # Grounding ratio is the groundedness score on a 0.0–1.0 scale.
        for ratio in (0.0, 0.5, 0.75, 1.0):
            evaluator = _make_evaluator(_recorded_response(groundedness=ratio))
            score = await evaluator.evaluate(_contract(), _artifact())
            assert 0.0 <= score.groundedness <= 1.0
            assert score.groundedness == ratio

    async def test_exactly_at_threshold_is_grounded_enough(self) -> None:
        evaluator = _make_evaluator(_recorded_response(groundedness=0.75))

        score = await evaluator.evaluate(_contract(), _artifact())

        assert score.groundedness == 0.75
        # All other dims are well above threshold, so the only gate is groundedness.
        assert score.passed is True

    async def test_missing_groundedness_defaults_to_grounded(self) -> None:
        # Pre-v2 responses omit the field; the evaluator must remain compatible
        # (default 1.0) rather than crash or silently fail the build.
        legacy = json.dumps(
            {
                "quality": 0.9,
                "originality": 0.9,
                "craft": 0.9,
                "functionality": 0.9,
                "feedback": "legacy response without groundedness",
                "criteria_results": {},
            }
        )
        evaluator = _make_evaluator(legacy)

        score = await evaluator.evaluate(_contract(), _artifact())

        assert score.groundedness == 1.0
        assert score.passed is True


# ── Live layer (requires ANTHROPIC_API_KEY; auto-skipped otherwise) ───────────


@pytest.mark.model_contract
def test_model_grounds_claims_in_provided_sources(
    anthropic_client: object,
    model_id: str,
) -> None:
    """A real model, asked to summarise only from a provided source, must not
    invent facts beyond it (and should hedge when the answer is not present)."""
    import anthropic

    client: anthropic.Anthropic = anthropic_client  # type: ignore[assignment]

    source = (
        "SOURCE DOCUMENT (the only ground truth):\n"
        "The export endpoint is POST /v1/reports/export and returns columns: "
        "id, created_at, total.\n"
    )
    response = client.messages.create(
        model=model_id,
        max_tokens=256,
        system=(
            "Answer ONLY from the SOURCE DOCUMENT. If the answer is not in it, say "
            "you cannot determine it from the source. Do not invent fields or methods."
        ),
        messages=[
            {
                "role": "user",
                "content": f"{source}\nWhat authentication scheme does the export endpoint use?",
            }
        ],
    )
    text = response.content[0].text.lower()

    # The source says nothing about auth — a grounded model must hedge, not invent.
    hedges = (
        "cannot",
        "not in",
        "no information",
        "does not",
        "unable",
        "not specified",
        "not mention",
    )
    assert any(h in text for h in hedges), (
        f"Model invented an unsupported auth claim instead of hedging. Response: {text[:400]!r}"
    )
