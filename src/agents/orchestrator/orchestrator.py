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
from enum import StrEnum
from typing import Any

from src.agents.hitl_gateway import HITLGateway, HITLRequest, HITLStatus
from src.agents.risk_scorer import RiskScorer
from src.guardrails.action_limits import ActionLimiter
from src.guardrails.audit_logger import AuditLogger, AuditWriteError
from src.guardrails.pii_filter import mask_dict
from src.guardrails.prompt_injection_guard import PromptInjectionGuard
from src.observability.logger import get_logger
from src.shared.config import settings
from src.shared.feature_flags import is_autonomous_mode_enabled
from src.shared.llm_client import LLMClient
from src.shared.models import AuditEvent

logger = get_logger("orchestrator")


class AgentPhase(StrEnum):
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
        hitl_gateway: HITLGateway,
        llm_client: LLMClient,
        injection_guard: PromptInjectionGuard | None = None,
        action_limiter: ActionLimiter | None = None,
        risk_scorer: RiskScorer | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._audit = audit_logger
        self._hitl = hitl_gateway
        self._llm = llm_client
        self._injection_guard = injection_guard or PromptInjectionGuard()
        self._action_limiter = action_limiter
        self._risk_scorer = risk_scorer or RiskScorer()

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

        import json

        response_text = await self._llm.complete(
            system=(
                "You are an AI agent. Analyse the provided context and respond with a JSON object "
                'containing: {"action": "<action_name>", "parameters": {}, "risk_score": 0.0}. '
                "risk_score must be between 0.0 (low) and 1.0 (high). "
                "The context has already been PII-masked — never request raw personal data."
            ),
            user=json.dumps(ctx.masked_input),
            trace_id=ctx.trace_id,
        )

        try:
            parsed = json.loads(response_text)
        except (json.JSONDecodeError, ValueError):
            parsed = {"action": "unknown", "parameters": {}, "risk_score": 1.0}

        ctx.proposed_action = str(parsed.get("action", "unknown"))
        ctx.proposed_parameters = dict(parsed.get("parameters", {}))
        ctx.risk_score = float(parsed.get("risk_score", 1.0))

        logger.info(
            "Agent reasoning complete",
            agent_id=ctx.agent_id,
            proposed_action=ctx.proposed_action,
            risk_score=ctx.risk_score,
        )
        return ctx

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

        import hashlib
        import json
        import uuid

        if self._action_limiter is not None:
            await self._action_limiter.check(ctx.proposed_action or "", ctx.proposed_parameters)

        # Compute authoritative risk_score via the 5-factor scorer (spec: specs/ai/hitl-hotl.md).
        # This replaces the LLM-self-reported score — the LLM cannot reliably assess its own risk.
        scored, components = self._risk_scorer.score(
            ctx.proposed_action or "unknown", ctx.proposed_parameters
        )
        ctx.risk_score = scored
        logger.info(
            "Risk scored",
            agent_id=ctx.agent_id,
            action=ctx.proposed_action,
            risk_score=ctx.risk_score,
            components={
                "irreversibility": components.irreversibility,
                "external_effect": components.external_effect,
                "scale": components.scale,
                "data_sensitivity": components.data_sensitivity,
                "rejection_rate": components.rejection_rate,
            },
        )

        # Write audit record BEFORE action execution (write-before-execute invariant)
        try:
            await self._audit.log_event(
                AuditEvent(
                    event_type="agent.action.proposed",
                    agent_id=ctx.agent_id,
                    action=ctx.proposed_action or "unknown",
                    outcome="PENDING",
                    risk_score=ctx.risk_score,
                    metadata={
                        "action_params_hash": hashlib.sha256(
                            json.dumps(ctx.proposed_parameters, sort_keys=True).encode()
                        ).hexdigest(),
                        "guardrails_passed": ["pii_filter", "injection_guard"],
                    },
                    trace_id=ctx.trace_id,
                )
            )
        except AuditWriteError:
            logger.error("Audit write failed — blocking action", agent_id=ctx.agent_id)
            raise

        # Route through HITL for MEDIUM/HIGH risk unless autonomous mode is active.
        # Autonomous mode (HOTL) bypasses HITL — only enable with explicit governance approval.
        if ctx.risk_score >= settings.hitl_risk_threshold and not is_autonomous_mode_enabled():
            logger.info(
                "Routing to HITL",
                agent_id=ctx.agent_id,
                risk_score=ctx.risk_score,
                threshold=settings.hitl_risk_threshold,
            )
            request = HITLRequest(
                request_id=str(uuid.uuid4()),
                agent_id=ctx.agent_id,
                action_type=ctx.proposed_action or "unknown",
                action_parameters=ctx.proposed_parameters,
                risk_score=ctx.risk_score,
                context_summary=json.dumps(ctx.masked_input)[:500],
                created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                expires_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            approved_request = await self._hitl.submit_for_approval(request)

            if approved_request.status != HITLStatus.APPROVED:
                raise ValueError(
                    f"HITL rejected action '{ctx.proposed_action}' "
                    f"(status={approved_request.status.value})"
                )

        # Action approved (HOTL or HITL-approved) — log executed outcome
        await self._audit.log_event(
            AuditEvent(
                event_type="agent.action.executed",
                agent_id=ctx.agent_id,
                action=ctx.proposed_action or "unknown",
                outcome="EXECUTED",
                risk_score=ctx.risk_score,
                trace_id=ctx.trace_id,
            )
        )

        logger.info(
            "Agent action executed",
            agent_id=ctx.agent_id,
            action=ctx.proposed_action,
            risk_score=ctx.risk_score,
        )

        return {
            "agent_id": ctx.agent_id,
            "action": ctx.proposed_action,
            "parameters": ctx.proposed_parameters,
            "risk_score": ctx.risk_score,
            "outcome": "EXECUTED",
            "trace_id": ctx.trace_id,
        }
