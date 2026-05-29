"""HarnessCoordinator — orchestrates the multi-agent harness pipeline.

Spec: specs/ai/harness-design.md §1.4 (HarnessCoordinator), §9 (Self-Reflection)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

Three modes (selected via settings.harness_mode):
  solo:        Route directly to AgentOrchestrator (no harness overhead).
  simplified:  Generator + Evaluator only (no Planner; single-sprint).
  full:        Planner → Generator + Evaluator with sprint decomposition.

Self-reflection (§9): after harness_patch_proposal_threshold failures, generate
a PatchProposal via LLM reflection before the final retry. Every sprint produces
an ExecutionSummary that is audit-logged and included in HITL escalation payloads.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from src.agents.harness.context_manager import ContextManager
from src.agents.harness.decision_tree_logger import DecisionTreeLogger
from src.agents.harness.evaluator import EvaluatorAgent
from src.agents.harness.models import (
    EvaluatorScore,
    ExecutionSummary,
    GeneratorArtifact,
    HarnessResult,
    PatchProposal,
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
            correlation_id=brief.correlation_id,
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
            correlation_id=brief.correlation_id,
        )

    async def _run_sprint(
        self,
        brief: TaskBrief,
        contract: SprintContract,
    ) -> tuple[GeneratorArtifact, EvaluatorScore | None, int, bool]:
        """Run generate → evaluate → retry loop for a single sprint.

        Self-reflection (§9): logs every decision bifurcation, generates a
        PatchProposal after harness_patch_proposal_threshold failures, and
        produces an ExecutionSummary at the end of the sprint regardless of outcome.

        Returns: (artifact, score, total_iterations, escalated_to_hitl)
        """
        last_artifact: GeneratorArtifact | None = None
        last_score: EvaluatorScore | None = None
        failures: list[str] = []
        patch_proposals_applied = 0
        dt_logger = DecisionTreeLogger(
            audit_logger=self._audit,
            agent_id="harness.coordinator",
            task_id=brief.task_id,
        )

        for iteration in range(1, settings.harness_max_iterations + 1):
            # Self-reflection: generate PatchProposal once threshold is crossed
            patch_proposal: PatchProposal | None = None
            threshold = settings.harness_patch_proposal_threshold
            if threshold > 0 and last_score is not None and (iteration - 1) >= threshold:
                patch_proposal = await self._generate_patch_proposal(
                    contract, last_score, iteration
                )
                patch_proposals_applied += 1
                await dt_logger.log(
                    decision_point=f"patch_proposal_iteration_{iteration}",
                    options_considered=["continue_with_feedback", "generate_patch_proposal"],
                    option_chosen="generate_patch_proposal",
                    rationale=(
                        f"Failed {iteration - 1} iteration(s); applying structured "
                        "self-reflection before retry."
                    ),
                    trace_id=brief.trace_id,
                )
            else:
                await dt_logger.log(
                    decision_point=f"generation_strategy_iteration_{iteration}",
                    options_considered=["fresh_generation", "feedback_incorporation"],
                    option_chosen="fresh_generation"
                    if last_score is None
                    else "feedback_incorporation",
                    rationale=(
                        "First attempt — no prior feedback available."
                        if last_score is None
                        else f"Incorporating evaluator feedback from iteration {iteration - 1}."
                    ),
                    trace_id=brief.trace_id,
                )

            artifact = await self._generate(brief, contract, last_score, patch_proposal)
            last_artifact = artifact

            if not settings.harness_evaluator_enabled:
                logger.warning("Evaluator disabled via config — auto-passing sprint")
                summary = self._build_execution_summary(
                    brief, contract, iteration, failures, patch_proposals_applied, None, dt_logger
                )
                await self._log_execution_summary(summary, brief.trace_id)
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
                summary = self._build_execution_summary(
                    brief, contract, iteration, failures, patch_proposals_applied, score, dt_logger
                )
                await self._log_execution_summary(summary, brief.trace_id)
                return artifact, score, iteration, False

            failures.append(
                f"iteration_{iteration}: score={score.average:.2f} feedback={score.feedback[:100]}"
            )
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
                summary = self._build_execution_summary(
                    brief, contract, iteration, failures, patch_proposals_applied, score, dt_logger
                )
                await self._log_execution_summary(summary, brief.trace_id)
                await self._escalate_to_hitl(brief, contract, artifact, score, summary)
                return artifact, score, iteration, True

        # Should not be reachable, but satisfies the type checker
        fallback = last_artifact or GeneratorArtifact(sprint_id=contract.sprint_id)
        return fallback, last_score, 0, False

    async def _generate(
        self,
        brief: TaskBrief,
        contract: SprintContract,
        previous_score: EvaluatorScore | None,
        patch_proposal: PatchProposal | None = None,
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

        patch_section = ""
        if patch_proposal is not None:
            patch_section = (
                f"\n\nSelf-reflection identified the following issue with the previous approach:\n"
                f"  Previous approach: {patch_proposal.previous_approach_summary}\n"
                f"  Proposed alternative: {patch_proposal.proposed_alternative}\n"
                f"  Reasoning: {patch_proposal.reasoning}\n"
                f"You MUST use the proposed alternative approach."
            )

        prompt = (
            f"Implement the following sprint:\n\n"
            f"Objectives:\n{objectives_text}\n\n"
            f"Success Criteria:\n{criteria_text}"
            f"{feedback_section}"
            f"{patch_section}"
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

    async def _generate_patch_proposal(
        self,
        contract: SprintContract,
        last_score: EvaluatorScore,
        iteration: int,
    ) -> PatchProposal:
        """LLM self-reflection: summarise the failed approach and propose a concrete alternative."""
        masked_feedback = mask_text(last_score.feedback)
        criteria_text = "\n".join(f"  - {c}" for c in contract.success_criteria)

        prompt = (
            f"You are a senior engineer performing structured self-reflection "
            f"on a failed sprint.\n\n"
            f"The sprint has failed {iteration - 1} time(s).\n\n"
            f"Success Criteria:\n{criteria_text}\n\n"
            f"Last evaluator feedback:\n{masked_feedback}\n\n"
            "Summarise the previous approach's failure in one sentence, then propose a "
            "concretely different alternative approach.\n\n"
            "Respond with valid JSON only:\n"
            '{"previous_approach_summary": "...", "proposed_alternative": "...", '
            '"reasoning": "..."}'
        )

        response = await self._llm.complete(
            system="You are a senior engineer performing structured self-reflection.",
            user=prompt,
            trace_id=None,
        )

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            data = {
                "previous_approach_summary": masked_feedback[:200],
                "proposed_alternative": (
                    "Attempt a fundamentally different implementation strategy."
                ),
                "reasoning": "LLM reflection response could not be parsed; using fallback.",
            }

        return PatchProposal(
            sprint_id=contract.sprint_id,
            iteration=iteration,
            previous_approach_summary=str(data.get("previous_approach_summary", "")),
            proposed_alternative=str(data.get("proposed_alternative", "")),
            reasoning=str(data.get("reasoning", "")),
        )

    def _build_execution_summary(
        self,
        brief: TaskBrief,
        contract: SprintContract,
        total_iterations: int,
        failures: list[str],
        patch_proposals_applied: int,
        final_score: EvaluatorScore | None,
        dt_logger: DecisionTreeLogger,
    ) -> ExecutionSummary:
        return ExecutionSummary(
            task_id=brief.task_id,
            sprint_id=contract.sprint_id,
            total_iterations=total_iterations,
            failures=list(failures),
            patch_proposals_applied=patch_proposals_applied,
            final_score=final_score,
            decisions=dt_logger.get_decisions(),
            generated_at=datetime.now(UTC).isoformat(),
            correlation_id=brief.correlation_id,
        )

    async def _log_execution_summary(
        self,
        summary: ExecutionSummary,
        trace_id: str | None = None,
    ) -> None:
        await self._audit.log_event(
            AuditEvent(
                event_type="agent.action.executed",
                agent_id="harness.coordinator",
                action="sprint_execution_summary",
                outcome="EXECUTED",
                metadata={
                    "task_id": summary.task_id,
                    "sprint_id": summary.sprint_id,
                    "total_iterations": summary.total_iterations,
                    "failures_count": len(summary.failures),
                    "patch_proposals_applied": summary.patch_proposals_applied,
                    "final_score": summary.final_score.average if summary.final_score else None,
                    "final_passed": summary.final_score.passed if summary.final_score else None,
                    "decision_count": len(summary.decisions),
                    "correlation_id": getattr(summary, "correlation_id", None),
                },
                trace_id=trace_id,
            )
        )

    async def _escalate_to_hitl(
        self,
        brief: TaskBrief,
        contract: SprintContract,
        artifact: GeneratorArtifact,
        score: EvaluatorScore,
        summary: ExecutionSummary | None = None,
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

        # Attach ExecutionSummary so the human reviewer has full iteration history
        if summary is not None:
            hitl_payload["execution_summary"] = {
                "total_iterations": summary.total_iterations,
                "failures_count": len(summary.failures),
                "patch_proposals_applied": summary.patch_proposals_applied,
                "decision_count": len(summary.decisions),
                "failures": summary.failures[:10],  # cap for payload size
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
