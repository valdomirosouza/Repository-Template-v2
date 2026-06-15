"""PlannerAgent — converts a TaskBrief into a ProductSpec with SprintContracts.

Spec: specs/ai/harness-design.md §1.1 (PlannerAgent)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

Prompt engineering invariants (from spec):
  - Focus on scope ambition, not implementation details.
  - Each sprint contract must have independently testable success criteria.
  - Surface AI feature opportunities explicitly.
  - Do NOT pre-select technology choices unless the brief demands it.

Safety gates (in order):
  1. pii_filter.mask_dict() on TaskBrief fields.
  2. injection_guard.validate() on masked description.
  3. audit_logger.log_event() before returning.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from src.agents.harness.models import ProductSpec, SprintContract, TaskBrief
from src.agents.prompt_loader import load_prompt
from src.guardrails.audit_logger import AuditLogger, AuditWriteError
from src.guardrails.pii_filter import mask_dict
from src.guardrails.prompt_injection_guard import PromptInjectionGuard
from src.observability.logger import get_logger
from src.shared.models import AuditEvent

logger = get_logger("harness.planner")

# Externalised to prompts/harness/planner.v1.md (ADR-0079). Loaded byte-for-byte;
# behaviour is unchanged vs the previously-inline constant.
_SYSTEM_PROMPT = load_prompt("harness.planner")


class PlannerAgent:
    """Converts a TaskBrief into a ProductSpec with ordered SprintContracts.

    Spec: specs/ai/harness-design.md §1.1
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        llm_client: Any,
        injection_guard: PromptInjectionGuard | None = None,
    ) -> None:
        self._audit = audit_logger
        self._llm = llm_client
        self._guard = injection_guard or PromptInjectionGuard()

    async def plan(self, brief: TaskBrief) -> ProductSpec:
        """Convert a TaskBrief into a ProductSpec.

        Raises:
            ValueError: if the brief fails injection guard validation.
            AuditWriteError: if audit logging fails (blocks the operation).
        """
        # Gate 1: mask PII
        masked_fields = mask_dict({"description": brief.description})
        masked_description = masked_fields["description"]

        # Gate 2: injection guard
        validation = self._guard.validate(masked_description)
        if not validation.is_valid:
            logger.warning(
                "Planner input rejected by injection guard",
                task_id=brief.task_id,
                reason=str(validation.rejection_reason),
            )
            raise ValueError(f"Planner input rejected: {validation.rejection_reason}")

        logger.info("Planner starting", task_id=brief.task_id, complexity=brief.complexity)

        # LLM call with masked context only
        response_text = await self._llm.complete(
            system=_SYSTEM_PROMPT,
            user=f"Brief: {masked_description}\nComplexity: {brief.complexity}",
            trace_id=brief.trace_id,
        )

        spec = self._parse_response(brief.task_id, response_text)

        # Gate 3: audit log before returning
        try:
            await self._audit.log_event(
                AuditEvent(
                    event_type="agent.action.executed",
                    agent_id="planner",
                    action="plan_generated",
                    outcome="EXECUTED",
                    metadata={
                        "task_id": brief.task_id,
                        "sprint_count": len(spec.sprint_contracts),
                        "ai_opportunities": len(spec.ai_feature_opportunities),
                    },
                    trace_id=brief.trace_id,
                )
            )
        except AuditWriteError:
            logger.error(
                "Audit write failed in planner — blocking plan return",
                task_id=brief.task_id,
            )
            raise

        logger.info(
            "Planner completed",
            task_id=brief.task_id,
            sprint_count=len(spec.sprint_contracts),
        )

        return spec

    def _parse_response(self, task_id: str, response_text: str) -> ProductSpec:
        """Parse LLM JSON response into a typed ProductSpec."""
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Planner LLM returned invalid JSON: {exc}") from exc

        contracts = [
            SprintContract(
                sprint_id=c.get("sprint_id", str(uuid.uuid4())),
                objectives=c.get("objectives", []),
                success_criteria=c.get("success_criteria", []),
            )
            for c in data.get("sprint_contracts", [])
        ]

        return ProductSpec(
            task_id=task_id,
            detailed_description=data.get("detailed_description", ""),
            sprint_contracts=contracts,
            ai_feature_opportunities=data.get("ai_feature_opportunities", []),
        )
