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
from src.guardrails.audit_logger import AuditLogger, AuditWriteError
from src.observability.logger import get_logger
from src.shared.config import settings
from src.shared.models import AuditEvent

logger = get_logger("harness.evaluator")

_SYSTEM_PROMPT = """\
You are a skeptical senior engineer performing a rigorous quality review.

Your DEFAULT assumption is that the implementation is INCOMPLETE or has DEFECTS.
Override this assumption only when you have actively confirmed correctness.

For each success criterion in the sprint contract:
  - Test it independently. Do not infer from reading code alone.
  - "This looks correct" is NOT sufficient. "I verified this works by X" is.
  - If you cannot confirm a criterion, it FAILS.

Score the implementation on four dimensions (0.0 to 1.0 each):
  - quality:       Functional coherence and completeness against the spec.
  - originality:   Evidence of deliberate design choices vs. template defaults.
  - craft:         Technical execution: error handling, edge cases, structure.
  - functionality: Every success criterion met independently and verifiably.

Passing threshold: all four dimensions must meet or exceed {threshold}.
A score of exactly {threshold} on any dimension is passing; below is not.

Respond with valid JSON:
{{
  "quality": <float 0.0-1.0>,
  "originality": <float 0.0-1.0>,
  "craft": <float 0.0-1.0>,
  "functionality": <float 0.0-1.0>,
  "feedback": "<specific, actionable feedback — what failed and why>",
  "criteria_results": {{
    "<criterion text>": true|false
  }}
}}
"""


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
