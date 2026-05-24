"""Agent orchestrator — Perception → Reason → Act loop.

Spec: specs/ai/agent-design.md
ADR:  ADR-0010 (Agent Framework Selection), ADR-0011 (HITL/HOTL Model)

The orchestrator coordinates the three phases of agent execution:

  Perception: receive and validate input context (PII masked)
  Reason:     call the LLM with masked context to produce a proposed action
  Act:        route the action through guardrails and HITL/HOTL gateway

Every phase emits OTel spans and Prometheus metrics.
All agent actions with real-world effects MUST route through HITLGateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.guardrails.action_limits import ActionLimitConfig, ActionLimiter
from src.guardrails.audit_logger import AuditLogger
from src.guardrails.pii_filter import mask_dict
from src.guardrails.prompt_injection_guard import PromptInjectionGuard
from src.observability.logger import get_logger

logger = get_logger("orchestrator")


class AgentPhase(str, Enum):
    PERCEPTION = "perception"
    REASON = "reason"
    ACT = "act"


@dataclass
class AgentContext:
    """Holds the masked, validated context for a single agent invocation."""

    agent_id: str
    raw_input: dict[str, Any]
    masked_input: dict[str, Any] = field(default_factory=dict)
    proposed_action: str | None = None
    proposed_parameters: dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0
    trace_id: str | None = None


class AgentOrchestrator:
    """Coordinates the Perception → Reason → Act loop for a single agent.

    Usage::

        orchestrator = AgentOrchestrator(
            agent_id="summariser-v1",
            audit_logger=audit,
            hitl_gateway=gateway,
        )
        result = await orchestrator.run(raw_input={"request_text": "..."})
    """

    def __init__(
        self,
        agent_id: str,
        audit_logger: AuditLogger,
        hitl_gateway: Any,  # HITLGateway — typed as Any to avoid circular import
        injection_guard: PromptInjectionGuard | None = None,
        action_limiter: ActionLimiter | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._audit = audit_logger
        self._hitl = hitl_gateway
        self._injection_guard = injection_guard or PromptInjectionGuard()
        self._action_limiter = action_limiter

    async def run(self, raw_input: dict[str, Any], trace_id: str | None = None) -> dict[str, Any]:
        """Execute the full Perception → Reason → Act loop.

        Returns the action outcome. Raises on guardrail failure or HITL rejection.
        """
        ctx = AgentContext(
            agent_id=self._agent_id,
            raw_input=raw_input,
            trace_id=trace_id,
        )

        ctx = await self._perceive(ctx)
        ctx = await self._reason(ctx)
        return await self._act(ctx)

    async def _perceive(self, ctx: AgentContext) -> AgentContext:
        """Phase 1: mask PII and validate input structure.

        Mandatory: PII masking before any further processing (ADR-0012).
        """
        logger.info("Agent perception phase", agent_id=ctx.agent_id, trace_id=ctx.trace_id)

        # L1: mask PII before any processing
        ctx.masked_input = mask_dict(ctx.raw_input)

        # L2: validate for injection attempts
        summary_text = str(ctx.masked_input)
        validation = self._injection_guard.validate(summary_text)
        if not validation.is_valid:
            logger.warning(
                "Input rejected by injection guard",
                agent_id=ctx.agent_id,
                reason=str(validation.rejection_reason),
            )
            raise ValueError(f"Input rejected: {validation.rejection_reason}")

        return ctx

    async def _reason(self, ctx: AgentContext) -> AgentContext:
        """Phase 2: call LLM with masked context to produce a proposed action.

        The LLM receives ONLY the masked context — never the raw input.
        """
        logger.info("Agent reasoning phase", agent_id=ctx.agent_id)

        # TODO: call LLM provider with ctx.masked_input as context
        # response = await llm_client.complete(prompt=build_prompt(ctx.masked_input))
        # ctx.proposed_action = response.action
        # ctx.proposed_parameters = response.parameters
        # ctx.risk_score = risk_scorer.score(ctx.proposed_action, ctx.proposed_parameters)

        raise NotImplementedError(
            "LLM reasoning not implemented. "
            "Implement _reason() by calling the configured LLM provider with ctx.masked_input."
        )

    async def _act(self, ctx: AgentContext) -> dict[str, Any]:
        """Phase 3: route proposed action through HITL/HOTL gateway and execute.

        All actions with real-world effects MUST route through HITLGateway (CLAUDE.md rule 3.3).
        """
        logger.info(
            "Agent act phase",
            agent_id=ctx.agent_id,
            proposed_action=ctx.proposed_action,
            risk_score=ctx.risk_score,
        )

        # TODO: submit to HITLGateway if risk_score >= threshold
        # if ctx.risk_score >= settings.hitl_risk_threshold:
        #     request = HITLRequest(...)
        #     approved_request = await self._hitl.submit_for_approval(request)
        #     # Block until decision or timeout (timeout → EXPIRED_AUTO_REJECTED)

        raise NotImplementedError(
            "Action execution not implemented. "
            "Implement _act() by routing through HITLGateway for consequential actions."
        )
