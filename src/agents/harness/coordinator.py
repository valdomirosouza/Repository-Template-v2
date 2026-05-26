"""HarnessCoordinator — orchestrates the multi-agent harness pipeline.

Spec: specs/ai/harness-design.md §1.4 (HarnessCoordinator)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

Three modes (selected via settings.harness_mode):
  solo:        Route directly to AgentOrchestrator (no harness overhead).
  simplified:  Generator + Evaluator only (no Planner; single-sprint).
  full:        Planner → Generator → Evaluator with sprint decomposition.

Escalation: if evaluator fails after harness_max_iterations, route to HITL gateway.
Context resets: ContextManager decides compaction vs reset at each agent boundary.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from src.agents.harness.context_manager import ContextManager
from src.agents.harness.evaluator import EvaluatorAgent
from src.agents.harness.models import (
    EvaluatorScore,
    GeneratorArtifact,
    HarnessResult,
    ProductSpec,
    SprintContract,
    TaskBrief,
)
from src.agents.harness.planner import PlannerAgent
from src.guardrails.audit_logger import AuditLogger
from src.guardrails.pii_filter import mask_dict, mask_text
from src.observability.logger import get_logger
from src.shared.config import settings
from src.shared.models import AuditEvent

logger = get_logger("harness.coordinator")


class HarnessCoordinator:
    """Routes tasks through the configured harness mode.

    Spec: specs/ai/harness-design.md §1.4
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        planner: PlannerAgent,
        evaluator: EvaluatorAgent,
        orchestrator: Any,  # AgentOrchestrator — Any to avoid circular import
        hitl_gateway: Any,  # HITLGateway
        llm_client: Any,
    ) -> None:
        self._audit = audit_logger
        self._planner = planner
        self._evaluator = evaluator
        self._orchestrator = orchestrator
        self._hitl = hitl_gateway
        self._llm = llm_client
        self._ctx_manager = ContextManager(reset_threshold=settings.harness_context_reset_threshold)

    async def run(self, brief: TaskBrief) -> HarnessResult:
        """Execute the harness pipeline for the given brief."""
        logger.info(
            "Harness coordinator starting",
            task_id=brief.task_id,
            mode=settings.harness_mode,
        )

        match settings.harness_mode:
            case "solo":
                return await self._run_solo(brief)
            case "simplified":
                return await self._run_simplified(brief)
            case "full":
                return await self._run_full(brief)
            case _:
                raise ValueError(f"Unknown harness_mode: {settings.harness_mode!r}")

    # ── solo ─────────────────────────────────────────────────────────────────

    async def _run_solo(self, brief: TaskBrief) -> HarnessResult:
        """Bypass harness — delegate directly to the P→R→A orchestrator."""
        result = await self._orchestrator.run(
            raw_input={"request_text": brief.description},
            trace_id=brief.trace_id,
        )
        return HarnessResult(
            task_id=brief.task_id,
            mode="solo",
            total_iterations=1,
            artifacts=[
                GeneratorArtifact(
                    sprint_id="solo",
                    outputs={"result": str(result)},
                )
            ],
        )

    # ── simplified ───────────────────────────────────────────────────────────

    async def _run_simplified(self, brief: TaskBrief) -> HarnessResult:
        """Generator + Evaluator only — no Planner, single sprint."""
        masked_description = mask_text(brief.description)
        criteria = brief.success_criteria or [
            f"The response is non-empty and directly addresses the stated task: "
            f"'{mask_text(brief.description[:200])}'"
        ]
        contract = SprintContract(
            sprint_id=str(uuid.uuid4()),
            objectives=[masked_description],
            success_criteria=criteria,
        )

        spec = ProductSpec(
            task_id=brief.task_id,
            detailed_description=masked_description,
            sprint_contracts=[contract],
        )

        return await self._execute_sprints(brief, spec, mode="simplified")

    # ── full ─────────────────────────────────────────────────────────────────

    async def _run_full(self, brief: TaskBrief) -> HarnessResult:
        """Planner → Generator → Evaluator with sprint decomposition."""
        if not settings.harness_planner_enabled:
            logger.warning("Planner disabled via config — falling back to simplified mode")
            return await self._run_simplified(brief)

        spec = await self._planner.plan(brief)

        # Optional HITL review of the ProductSpec before execution
        if settings.harness_planner_hitl_review:
            await self._review_spec_with_hitl(brief, spec)

        return await self._execute_sprints(brief, spec, mode="full")

    # ── shared sprint loop ────────────────────────────────────────────────────

    async def _execute_sprints(
        self,
        brief: TaskBrief,
        spec: ProductSpec,
        mode: str,
    ) -> HarnessResult:
        """Iterate over sprint contracts, evaluate, and retry until pass or escalation."""
        all_artifacts: list[GeneratorArtifact] = []
        final_score = None
        total_iterations = 0
        escalated = False

        for contract in spec.sprint_contracts:
            artifact, score, iterations, did_escalate = await self._run_sprint(brief, contract)
            all_artifacts.append(artifact)
            final_score = score
            total_iterations += iterations
            if did_escalate:
                escalated = True
                break  # stop on first HITL escalation

        return HarnessResult(
            task_id=brief.task_id,
            mode=mode,  # type: ignore[arg-type]
            total_iterations=total_iterations,
            artifacts=all_artifacts,
            final_score=final_score,
            escalated_to_hitl=escalated,
        )

    async def _run_sprint(
        self,
        brief: TaskBrief,
        contract: SprintContract,
    ) -> tuple[GeneratorArtifact, EvaluatorScore | None, int, bool]:
        """Run generate → evaluate → retry loop for a single sprint.

        Returns: (artifact, score, total_iterations, escalated_to_hitl)
        """
        last_artifact: GeneratorArtifact | None = None
        last_score: EvaluatorScore | None = None

        for iteration in range(1, settings.harness_max_iterations + 1):
            artifact = await self._generate(brief, contract, last_score)
            last_artifact = artifact

            if not settings.harness_evaluator_enabled:
                logger.warning("Evaluator disabled via config — auto-passing sprint")
                return artifact, None, iteration, False

            score = await self._evaluator.evaluate(contract, artifact, iteration=iteration)
            last_score = score

            if score.passed:
                logger.info(
                    "Sprint passed",
                    sprint_id=contract.sprint_id,
                    iteration=iteration,
                    average=round(score.average, 3),
                )
                return artifact, score, iteration, False

            logger.info(
                "Sprint failed — retrying",
                sprint_id=contract.sprint_id,
                iteration=iteration,
                average=round(score.average, 3),
            )

            if iteration == settings.harness_max_iterations:
                logger.warning(
                    "Max iterations reached — escalating to HITL",
                    sprint_id=contract.sprint_id,
                )
                await self._escalate_to_hitl(brief, contract, artifact, score)
                return artifact, score, iteration, True

        # Should not be reachable, but satisfies the type checker
        fallback = last_artifact or GeneratorArtifact(sprint_id=contract.sprint_id)
        return fallback, last_score, 0, False

    async def _generate(
        self,
        brief: TaskBrief,
        contract: SprintContract,
        previous_score: EvaluatorScore | None,
    ) -> GeneratorArtifact:
        """Call the LLM to generate artifacts for a sprint contract."""
        masked_objectives = [mask_text(o) for o in contract.objectives]
        masked_criteria = [mask_text(c) for c in contract.success_criteria]

        criteria_text = "\n".join(f"  - {c}" for c in masked_criteria)
        objectives_text = "\n".join(f"  - {o}" for o in masked_objectives)

        feedback_section = ""
        if previous_score is not None:
            masked_feedback = mask_text(previous_score.feedback)
            feedback_section = (
                f"\n\nPrevious attempt scored {previous_score.average:.2f}/1.0 and FAILED.\n"
                f"Evaluator feedback: {masked_feedback}\n"
                f"You must address this feedback in your new attempt."
            )

        prompt = (
            f"Implement the following sprint:\n\n"
            f"Objectives:\n{objectives_text}\n\n"
            f"Success Criteria:\n{criteria_text}"
            f"{feedback_section}"
        )

        response = await self._llm.complete(
            system="You are an expert software engineer implementing a product sprint.",
            user=prompt,
            trace_id=brief.trace_id,
        )

        return GeneratorArtifact(
            sprint_id=contract.sprint_id,
            outputs={"implementation": response},
        )

    async def _escalate_to_hitl(
        self,
        brief: TaskBrief,
        contract: SprintContract,
        artifact: GeneratorArtifact,
        score: EvaluatorScore,
    ) -> None:
        """Escalate to HITL gateway after max iterations without passing."""
        await self._audit.log_event(
            AuditEvent(
                event_type="agent.action.proposed",
                agent_id="harness.coordinator",
                action="harness_hitl_escalation",
                outcome="PENDING",
                metadata={
                    "task_id": brief.task_id,
                    "sprint_id": contract.sprint_id,
                    "final_iteration": score.iteration,
                    "final_score": score.average,
                    "evaluator_feedback": score.feedback,
                },
                trace_id=brief.trace_id,
            )
        )

        # Build HITL request payload for human reviewer
        hitl_payload: dict[str, Any] = {
            "sprint_contract": {
                "sprint_id": contract.sprint_id,
                "objectives": contract.objectives,
                "success_criteria": contract.success_criteria,
            },
            "last_artifact_summary": {k: v[:500] for k, v in artifact.outputs.items()},
            "evaluator_score": {
                "quality": score.quality,
                "originality": score.originality,
                "craft": score.craft,
                "functionality": score.functionality,
                "average": score.average,
                "feedback": score.feedback,
                "iteration": score.iteration,
            },
        }

        hitl_payload = mask_dict(hitl_payload)

        logger.warning(
            "Harness escalating to HITL",
            task_id=brief.task_id,
            sprint_id=contract.sprint_id,
            payload_summary=json.dumps(hitl_payload)[:200],
        )

        # Route through HITLGateway — blocks until human decision or timeout
        from src.agents.hitl_gateway import HITLRequest

        now = datetime.now(UTC)
        request = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="harness.coordinator",
            action_type="harness_sprint_escalation",
            action_parameters=hitl_payload,
            risk_score=1.0,
            context_summary=json.dumps(hitl_payload)[:500],
            created_at=now,
            expires_at=now + timedelta(seconds=settings.hitl_approval_timeout_seconds),
        )
        await self._hitl.submit_for_approval(request)

    async def _review_spec_with_hitl(self, brief: TaskBrief, spec: ProductSpec) -> None:
        """Optional HITL review of ProductSpec before sprint execution begins."""

        await self._audit.log_event(
            AuditEvent(
                event_type="agent.action.proposed",
                agent_id="harness.coordinator",
                action="planner_spec_review",
                outcome="PENDING",
                metadata={
                    "task_id": brief.task_id,
                    "sprint_count": len(spec.sprint_contracts),
                },
                trace_id=brief.trace_id,
            )
        )

        from src.agents.hitl_gateway import HITLRequest

        spec_payload: dict[str, Any] = {
            "detailed_description": spec.detailed_description[:1000],
            "sprint_contracts": [
                {"sprint_id": c.sprint_id, "objectives": c.objectives}
                for c in spec.sprint_contracts
            ],
        }
        spec_payload = mask_dict(spec_payload)
        now = datetime.now(UTC)
        request = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="harness.coordinator",
            action_type="planner_spec_review",
            action_parameters=spec_payload,
            risk_score=0.5,
            context_summary=json.dumps(spec_payload)[:500],
            created_at=now,
            expires_at=now + timedelta(seconds=settings.hitl_approval_timeout_seconds),
        )
        await self._hitl.submit_for_approval(request)
