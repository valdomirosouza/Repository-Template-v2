"""EvaluatorAgent — external quality gate with explicit skepticism.

Spec: specs/ai/harness-design.md §1.3 (EvaluatorAgent)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

Core insight (from Anthropic Engineering article):
  Agents tend to respond by confidently praising their own work, even when
  quality is mediocre. An external evaluator tuned to skepticism is required
  to break this self-praise bias.

Skepticism rules (enforced via system prompt):
  - Default assumption: the implementation has defects.
  - Each success_criteria item is verified independently.
  - "This looks like it would work" → passed = False.
  - Score below harness_evaluator_pass_threshold on ANY dimension → passed = False.

Safety gates:
  - audit_logger.log_event() with all four scores before returning.
  - OTel span evaluator.completed.
"""

from __future__ import annotations

import json
from typing import Any

from src.agents.harness.models import EvaluatorScore, GeneratorArtifact, SprintContract
from src.agents.prompts import load_prompt
from src.guardrails.audit_logger import AuditLogger, AuditWriteError
from src.observability.logger import get_logger
from src.observability.metrics import record_groundedness
from src.shared.config import settings
from src.shared.models import AuditEvent

logger = get_logger("harness.evaluator")

# Externalised, versioned prompt (ADR-0079). Loaded once at import; byte-identical
# to the former inline constant, so `.format(threshold=...)` below is unchanged.
_SYSTEM_PROMPT = load_prompt("harness.evaluator")


class EvaluatorAgent:
    """Scores a GeneratorArtifact against a SprintContract.

    Spec: specs/ai/harness-design.md §1.3
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        llm_client: Any,
    ) -> None:
        self._audit = audit_logger
        self._llm = llm_client
        self._threshold = settings.harness_evaluator_pass_threshold

    async def evaluate(
        self,
        contract: SprintContract,
        artifact: GeneratorArtifact,
        iteration: int = 1,
    ) -> EvaluatorScore:
        """Score the artifact against the sprint contract.

        Raises:
            AuditWriteError: if audit logging fails (blocks evaluation result).
        """
        logger.info(
            "Evaluator starting",
            sprint_id=contract.sprint_id,
            iteration=iteration,
            criteria_count=len(contract.success_criteria),
        )

        user_message = self._build_user_message(contract, artifact)

        system = _SYSTEM_PROMPT.format(threshold=self._threshold)
        response_text = await self._llm.complete(system=system, user=user_message)

        score = self._parse_response(contract.sprint_id, response_text, iteration)

        # Groundedness SLI (ADR-0080): reuse this SAME LLM call's JSON — no extra
        # model call. Emitted as a SEPARATE metric, never a 5th EvaluatorScore
        # dimension and never part of the `passed` rule. Backward-compatible: if
        # the field is absent or non-numeric (e.g. v1 prompt), recording is
        # skipped rather than fabricated.
        groundedness = self._emit_groundedness(contract.sprint_id, response_text)

        # Audit log with all four dimension scores — before returning
        try:
            await self._audit.log_event(
                AuditEvent(
                    event_type="agent.action.executed",
                    agent_id="evaluator",
                    action="evaluation_completed",
                    outcome="EXECUTED",
                    metadata={
                        "sprint_id": contract.sprint_id,
                        "iteration": iteration,
                        "passed": score.passed,
                        "score_quality": score.quality,
                        "score_originality": score.originality,
                        "score_craft": score.craft,
                        "score_functionality": score.functionality,
                        "average": score.average,
                        # Side-metric (ADR-0080); None when the LLM omitted it.
                        "groundedness": groundedness,
                    },
                )
            )
        except AuditWriteError:
            logger.error(
                "Audit write failed in evaluator — blocking score return",
                sprint_id=contract.sprint_id,
            )
            raise

        logger.info(
            "Evaluator completed",
            sprint_id=contract.sprint_id,
            iteration=iteration,
            passed=score.passed,
            average=round(score.average, 3),
        )

        return score

    def _build_user_message(
        self,
        contract: SprintContract,
        artifact: GeneratorArtifact,
    ) -> str:
        criteria_text = "\n".join(f"  - {c}" for c in contract.success_criteria)
        objectives_text = "\n".join(f"  - {o}" for o in contract.objectives)

        artifact_summary = json.dumps(
            {path: content[:2000] for path, content in artifact.outputs.items()},
            indent=2,
        )

        return (
            f"Sprint Contract:\n"
            f"Objectives:\n{objectives_text}\n\n"
            f"Success Criteria:\n{criteria_text}\n\n"
            f"Generator Artifacts (truncated at 2000 chars per file):\n"
            f"{artifact_summary}"
        )

    def _parse_response(
        self,
        sprint_id: str,
        response_text: str,
        iteration: int,
    ) -> EvaluatorScore:
        """Parse LLM JSON response into a typed EvaluatorScore."""
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Evaluator LLM returned invalid JSON: {exc}") from exc

        quality = float(data.get("quality", 0.0))
        originality = float(data.get("originality", 0.0))
        craft = float(data.get("craft", 0.0))
        functionality = float(data.get("functionality", 0.0))

        passed = all(dim >= self._threshold for dim in (quality, originality, craft, functionality))

        return EvaluatorScore(
            sprint_id=sprint_id,
            quality=quality,
            originality=originality,
            craft=craft,
            functionality=functionality,
            passed=passed,
            feedback=data.get("feedback", ""),
            retry_required=not passed,
            iteration=iteration,
        )

    def _emit_groundedness(self, sprint_id: str, response_text: str) -> float | None:
        """Emit the groundedness SLI from the evaluator's own LLM response (ADR-0080).

        Groundedness is a separate safety metric — the LLM-judged share of the
        implementation's claims that trace to the provided spec/success-criteria.
        It is NOT an ``EvaluatorScore`` dimension and does not affect ``passed``.

        Backward-compatible by design: if the field is missing or non-numeric
        (e.g. the v1 prompt, or a malformed value), recording is skipped — never
        fabricated with a placeholder/constant. ``response_text`` has already
        parsed as JSON in ``_parse_response`` by the time this is called.
        """
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            return None

        raw = data.get("groundedness")
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            return None

        groundedness = float(raw)
        record_groundedness(
            score=groundedness,
            flagged=groundedness < self._threshold,
            agent_id="evaluator",
            sprint_id=sprint_id,
        )
        return groundedness
