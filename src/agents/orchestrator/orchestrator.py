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

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from src.agents.action_policy import requires_mandatory_hitl
from src.agents.compensation_registry import CompensationRegistry
from src.agents.feedback_learner import FeedbackLearner, default_feedback_learner
from src.agents.hitl_gateway import HITLGateway, HITLRequest, HITLStatus
from src.agents.hotl_monitor import HOTLMonitor
from src.agents.prompts import load_prompt
from src.agents.risk_scorer import RiskScorer
from src.agents.schemas import parse_agent_action
from src.agents.spec_contract_enforcer import SpecContractEnforcer, SpecViolationError
from src.agents.tool_executor import ToolExecutor
from src.guardrails.action_limits import ActionLimiter
from src.guardrails.audit_logger import AuditLogger, AuditWriteError
from src.guardrails.output_sanitizer import sanitize_output
from src.guardrails.pii_filter import mask_dict
from src.guardrails.prompt_injection_guard import PromptInjectionGuard
from src.observability.logger import get_logger
from src.observability.span_hierarchy import (
    SPAN_AGENT_ACT,
    SPAN_AGENT_PERCEIVE,
    SPAN_AGENT_REASON,
    SPAN_AGENT_TASK,
    tracer,
)
from src.shared.config import settings
from src.shared.feature_flags import get_autonomy_level, get_learning_mode
from src.shared.llm_client import LLMClient
from src.shared.models import AuditEvent

logger = get_logger("orchestrator")

# Externalised, versioned base Reason-phase prompt (ADR-0079). Byte-identical to the
# former inline constant; the dynamic precedents + spec-contract blocks are still
# assembled in `_reason` below. strip_trailing_newline keeps it equal to the old
# string (which had no trailing newline) before those blocks are appended.
_REASON_BASE_SYSTEM_PROMPT = load_prompt("orchestrator.reason", strip_trailing_newline=True)


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
    # agent_action_v1 schema validity (ADR-0054); invalid output must not silently proceed
    schema_valid: bool = True
    schema_errors: list[str] = field(default_factory=list)


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
        feedback_learner: FeedbackLearner | None = None,
        spec_contract_enforcer: SpecContractEnforcer | None = None,
        tool_executor: ToolExecutor | None = None,
        compensation_registry: CompensationRegistry | None = None,
        hotl_monitor: HOTLMonitor | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._audit = audit_logger
        self._hitl = hitl_gateway
        self._llm = llm_client
        self._injection_guard = injection_guard or PromptInjectionGuard()
        self._action_limiter = action_limiter
        self._risk_scorer = risk_scorer or RiskScorer()
        self._learner = feedback_learner or default_feedback_learner
        self._spec_enforcer = spec_contract_enforcer
        self._tool_executor = tool_executor or ToolExecutor(audit_logger=audit_logger)
        # HOTL reversibility gate (ADR-0055): non-reversible / over-ceiling actions
        # cannot run autonomously under HOTL — they fall back to HITL.
        self._compensation_registry = compensation_registry or CompensationRegistry()
        # Optional HOTL post-execution lifecycle (notify + override window). When None,
        # behaviour is unchanged (no notification / window is opened).
        self._hotl_monitor = hotl_monitor

    async def run(self, raw_input: dict[str, Any], trace_id: str | None = None) -> dict[str, Any]:
        """Execute the full Perception → Reason → Act loop.

        Returns the action outcome. Raises on guardrail failure or HITL rejection.
        """
        with tracer.start_as_current_span(SPAN_AGENT_TASK) as span:
            span.set_attributes(
                {
                    "agent.task_id": trace_id or "",
                    "agent.session_id": trace_id or "",
                    "agent.id": self._agent_id,
                    "agent.harness_mode": settings.harness_mode,
                }
            )
            ctx = AgentContext(
                agent_id=self._agent_id,
                raw_input=raw_input,
                trace_id=trace_id,
            )
            try:
                ctx = await self._perceive(ctx)
                ctx = await self._reason(ctx)
                return await self._act(ctx)
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                raise

    async def _perceive(self, ctx: AgentContext) -> AgentContext:
        """Phase 1: mask PII and validate input structure.

        Mandatory: PII masking before any further processing (ADR-0012).
        """
        with tracer.start_as_current_span(SPAN_AGENT_PERCEIVE) as span:
            logger.info("Agent perception phase", agent_id=ctx.agent_id, trace_id=ctx.trace_id)

            # L1: mask PII before any processing
            ctx.masked_input = mask_dict(ctx.raw_input)
            pii_fields_masked = len(ctx.raw_input) - len(
                [k for k in ctx.raw_input if ctx.raw_input[k] == ctx.masked_input.get(k)]
            )

            # L2: validate for injection attempts
            summary_text = str(ctx.masked_input)
            validation = self._injection_guard.validate(summary_text)

            span.set_attributes(
                {
                    "perceive.pii_fields_masked": pii_fields_masked,
                    "perceive.injection_guard_passed": validation.is_valid,
                    "perceive.injection_risk_score": float(
                        getattr(validation, "risk_score", 0.0) or 0.0
                    ),
                }
            )

            if not validation.is_valid:
                span.set_status(StatusCode.ERROR, "injection guard rejected input")
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
        with tracer.start_as_current_span(SPAN_AGENT_REASON) as span:
            logger.info("Agent reasoning phase", agent_id=ctx.agent_id)

            import json

            # Learn stage: inject precedents into system prompt when learning-mode=active.
            learning_mode = get_learning_mode()
            precedents_block = self._learner.build_precedents_block(
                action_type=str(ctx.masked_input.get("action_type", "")),
                payload_hash="",
                mode=learning_mode,
            )
            precedents_injected = bool(precedents_block)

            system_prompt = _REASON_BASE_SYSTEM_PROMPT
            if precedents_block:
                system_prompt = f"{system_prompt}\n\n{precedents_block}"
            # Inject spec contract boundary so LLM is aware of its permission scope (SD1).
            if self._spec_enforcer is not None:
                system_prompt = self._spec_enforcer.inject_contract(system_prompt)

            response_text = await self._llm.complete(
                system=system_prompt,
                user=json.dumps(ctx.masked_input),
                trace_id=ctx.trace_id,
            )

            # Validate against the agent_action_v1 envelope (ADR-0054). Invalid output
            # never silently proceeds — it is routed to HITL or blocked in _act_inner.
            action = parse_agent_action(response_text)
            ctx.proposed_action = action.action_type
            # Merge structured envelope fields so risk_scorer + action_policy can read them.
            ctx.proposed_parameters = action.merged_parameters()
            ctx.schema_valid = action.is_valid
            ctx.schema_errors = action.validation_errors
            # LLM-self-reported confidence is advisory only; the system scorer owns the
            # final risk score (set in _act_inner).
            ctx.risk_score = 1.0

            if not action.is_valid:
                logger.warning(
                    "Agent output failed agent_action_v1 validation",
                    agent_id=ctx.agent_id,
                    action_type=ctx.proposed_action,
                    errors=action.validation_errors,
                )

            span.set_attributes(
                {
                    "reason.model": settings.llm_model,
                    "reason.precedents_injected": precedents_injected,
                    "reason.schema_valid": action.is_valid,
                    "reason.schema_legacy": action.legacy,
                }
            )

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
        with tracer.start_as_current_span(SPAN_AGENT_ACT) as span:
            return await self._act_inner(ctx, span)

    async def _act_inner(self, ctx: AgentContext, span: trace.Span) -> dict[str, Any]:
        logger.info(
            "Agent act phase",
            agent_id=ctx.agent_id,
            proposed_action=ctx.proposed_action,
            risk_score=ctx.risk_score,
        )

        import hashlib
        import json
        import uuid

        # Layer 5 — Output sanitization (OWASP LLM02/LLM05). Sanitize LLM-produced strings before
        # they are stored for HITL render, logged, or reach an execution sink. escape=False: control
        # chars are stripped and code-exec sinks detected (both safe on the execution path), but
        # markup is NOT escaped here (that would corrupt executable parameter values — render
        # consumers escape at display time). Detected sinks force HITL below. Strengthens, never
        # replaces, the input-side prompt-injection guard.
        sanitized_params, sani_report = sanitize_output(ctx.proposed_parameters)
        ctx.proposed_parameters = sanitized_params
        if sani_report.modified:
            logger.warning(
                "output_sanitizer.modified",
                agent_id=ctx.agent_id,
                control_chars_stripped=sani_report.control_chars_stripped,
                fields_escaped=sani_report.fields_escaped,
                sinks_detected=sani_report.sinks_detected,
            )
            span.set_attribute("act.output_sanitized", True)
            span.set_attribute(
                "act.output_control_chars_stripped", sani_report.control_chars_stripped
            )
            if sani_report.sinks_detected:
                span.set_attribute(
                    "act.output_sinks_detected", ",".join(sani_report.sinks_detected)
                )

        if self._action_limiter is not None:
            await self._action_limiter.check(ctx.proposed_action or "", ctx.proposed_parameters)

        # Validate proposed action against the spec contract boundary (SD1 — ADR-0047).
        if self._spec_enforcer is not None:
            try:
                self._spec_enforcer.validate_action(ctx.proposed_action or "unknown")
            except SpecViolationError as exc:
                logger.warning(
                    "spec_contract.violation",
                    agent_id=ctx.agent_id,
                    action=ctx.proposed_action,
                    reason=str(exc),
                )
                span.set_attribute("act.spec_violation", True)
                raise

        # Compute authoritative risk_score via the 5-factor scorer (spec: specs/ai/hitl-hotl.md).
        # This replaces the LLM-self-reported score — the LLM cannot reliably assess its own risk.
        scored, components = self._risk_scorer.score(
            ctx.proposed_action or "unknown", ctx.proposed_parameters
        )
        ctx.risk_score = scored

        # P0-3: Mandatory HITL policy — evaluated BEFORE risk score.
        # Numeric score cannot downgrade mandatory categories (ADR-0053).
        mandatory_hitl, mandatory_reason = requires_mandatory_hitl(
            ctx.proposed_action or "unknown", ctx.proposed_parameters
        )

        # P0-2: Graduated autonomy decision — replaces boolean is_autonomous_mode_enabled().
        autonomy_level = get_autonomy_level(ctx.proposed_action or "unknown", ctx.risk_score)

        # P0-4: Tool registry + autonomy gating informs the routing decision so the
        # ToolExecutor never has to contradict the orchestrator post-approval.
        action_name = ctx.proposed_action or "unknown"
        is_registered = self._tool_executor.is_registered(action_name)
        permits_autonomous = self._tool_executor.permits_autonomous(
            action_name, autonomy_level.value
        )

        # Full decision matrix (ADR-0053/0054, specs/ai/hitl-hotl.md):
        #   mandatory policy → HITL (numeric score cannot downgrade)
        #   unregistered     → blocked (no HITL bypass; ToolExecutor raises)
        #   schema invalid   → HITL (malformed agent output never proceeds silently)
        #   risk ≥ threshold → HITL
        #   autonomy permits → execute autonomously (HOTL)
        #   otherwise        → fall back to HITL (autonomy ceiling insufficient)
        if mandatory_hitl:
            route_to_hitl = True
            oversight_mode = "HITL_MANDATORY"
        elif not is_registered:
            route_to_hitl = False  # ToolExecutor step 2 blocks unregistered tools
            oversight_mode = "BLOCKED_UNREGISTERED"
        elif not ctx.schema_valid:
            route_to_hitl = True  # malformed agent_action_v1 output → human review
            oversight_mode = "HITL_SCHEMA_INVALID"
        elif sani_report.sinks_detected:
            # LLM02/LLM05: output containing a code-exec / active-content sink is never executed
            # autonomously — a human reviews it (the safe "block").
            route_to_hitl = True
            oversight_mode = "HITL_OUTPUT_SINK"
        elif ctx.risk_score >= settings.hitl_risk_threshold:
            route_to_hitl = True
            oversight_mode = "HITL"
        elif permits_autonomous:
            # HOTL reversibility gate (ADR-0055): a non-reversible action — or one
            # above the tool's HOTL risk ceiling — cannot run autonomously; it falls
            # back to HITL for explicit human approval.
            hotl_ok, hotl_reason = self._compensation_registry.can_run_under_hotl(
                action_name, ctx.risk_score
            )
            if hotl_ok:
                route_to_hitl = False
                oversight_mode = f"HOTL_{autonomy_level.name}"
            else:
                route_to_hitl = True
                oversight_mode = "HITL_NON_REVERSIBLE"
                logger.info(
                    "HOTL reversibility gate routed action to HITL",
                    agent_id=ctx.agent_id,
                    action=action_name,
                    reason=hotl_reason,
                )
        else:
            route_to_hitl = True
            oversight_mode = "HITL"

        span.set_attributes(
            {
                "act.action_type": ctx.proposed_action or "unknown",
                "act.risk_score": ctx.risk_score,
                "act.hitl_required": route_to_hitl,
                "act.autonomy_level": autonomy_level.value,
                "act.oversight_mode": oversight_mode,
                "act.mandatory_hitl": mandatory_hitl,
            }
        )
        logger.info(
            "Risk scored",
            agent_id=ctx.agent_id,
            action=ctx.proposed_action,
            risk_score=ctx.risk_score,
            autonomy_level=autonomy_level.value,
            oversight_mode=oversight_mode,
            mandatory_hitl=mandatory_hitl,
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
                        "autonomy_level": autonomy_level.value,
                        "oversight_mode": oversight_mode,
                        "mandatory_hitl": mandatory_hitl,
                        "mandatory_hitl_reason": mandatory_reason,
                    },
                    trace_id=ctx.trace_id,
                )
            )
        except AuditWriteError:
            logger.error("Audit write failed — blocking action", agent_id=ctx.agent_id)
            raise

        # Route through HITL gateway when required (P0-1 fix: return PENDING instead of failing).
        if route_to_hitl:
            logger.info(
                "Routing to HITL",
                agent_id=ctx.agent_id,
                risk_score=ctx.risk_score,
                oversight_mode=oversight_mode,
                mandatory=mandatory_hitl,
            )
            import datetime

            now = datetime.datetime.now(datetime.UTC)
            request = HITLRequest(
                request_id=str(uuid.uuid4()),
                agent_id=ctx.agent_id,
                action_type=ctx.proposed_action or "unknown",
                action_parameters=ctx.proposed_parameters,
                risk_score=ctx.risk_score,
                context_summary=json.dumps(ctx.masked_input)[:500],
                created_at=now,
                expires_at=now,
            )
            hitl_response = await self._hitl.submit_for_approval(request)

            # P0-1: Handle PENDING as a valid suspension state — not a failure.
            # The action will resume when POST /v1/hitl/{id}/decide delivers approval.
            if hitl_response.status == HITLStatus.PENDING:
                logger.info(
                    "HITL pending — suspending action",
                    agent_id=ctx.agent_id,
                    hitl_request_id=hitl_response.request_id,
                )
                return {
                    "status": "waiting_for_human_approval",
                    "hitl_request_id": hitl_response.request_id,
                    "action_type": ctx.proposed_action,
                    "risk_score": ctx.risk_score,
                    "outcome": "PENDING",
                    "agent_id": ctx.agent_id,
                    "trace_id": ctx.trace_id,
                    "oversight_mode": oversight_mode,
                }

            if hitl_response.status == HITLStatus.REJECTED:
                self._learner.record(
                    FeedbackLearner.feedback_from_hitl_decision(
                        action_type=ctx.proposed_action or "unknown",
                        action_parameters=ctx.proposed_parameters,
                        decision="rejected",
                        rationale="HITL reviewer rejected action",
                        agent_id=ctx.agent_id,
                    )
                )
                raise ValueError(
                    f"HITL rejected action '{ctx.proposed_action}' "
                    f"(hitl_request_id={hitl_response.request_id})"
                )

            if hitl_response.status == HITLStatus.EXPIRED:
                raise ValueError(
                    f"HITL request expired before decision for action '{ctx.proposed_action}' "
                    f"(hitl_request_id={hitl_response.request_id})"
                )

            # APPROVED — fall through to execution below

        # P0-4: Execute via ToolExecutor 10-step enforcement sequence.
        # When we routed through HITL and reached here, approval was granted —
        # pass hitl_approved so the executor does not re-block on requires_hitl /
        # autonomy-permission (registry + sandbox checks still apply).
        tool_result = await self._tool_executor.execute(
            action_type=ctx.proposed_action or "unknown",
            parameters=ctx.proposed_parameters,
            autonomy_level=autonomy_level.value,
            agent_id=ctx.agent_id,
            trace_id=ctx.trace_id,
            hitl_approved=route_to_hitl,
        )

        # ToolExecutor handles its own audit records (steps 8-10).
        # Log orchestrator-level executed outcome for span correlation.
        hotl_action_id: str | None = None
        if tool_result.outcome == "EXECUTED":
            logger.info(
                "Agent action executed",
                agent_id=ctx.agent_id,
                action=ctx.proposed_action,
                risk_score=ctx.risk_score,
                oversight_mode=oversight_mode,
                sandbox_used=tool_result.sandbox_used,
            )
            self._learner.record(
                FeedbackLearner.feedback_from_hitl_decision(
                    action_type=ctx.proposed_action or "unknown",
                    action_parameters=ctx.proposed_parameters,
                    decision="approved",
                    rationale=f"Executed under oversight_mode={oversight_mode}",
                    agent_id=ctx.agent_id,
                )
            )

            # HOTL lifecycle (ADR-0055): for autonomously-executed (HOTL) actions,
            # notify the reviewer and open the override window. Skipped when no
            # monitor is configured or the action went through HITL.
            if self._hotl_monitor is not None and oversight_mode.startswith("HOTL_"):
                hotl_action_id = str(uuid.uuid4())
                await self._hotl_monitor.on_hotl_executed(
                    action_id=hotl_action_id,
                    agent_id=ctx.agent_id,
                    action_type=ctx.proposed_action or "unknown",
                    parameters=ctx.proposed_parameters,
                    risk_score=ctx.risk_score,
                    oversight_mode=oversight_mode,
                    trace_id=ctx.trace_id,
                )

        result = {
            "agent_id": ctx.agent_id,
            "action": ctx.proposed_action,
            "parameters": ctx.proposed_parameters,
            "risk_score": ctx.risk_score,
            "outcome": tool_result.outcome,
            "oversight_mode": oversight_mode,
            "autonomy_level": autonomy_level.value,
            "sandbox_used": tool_result.sandbox_used,
            "trace_id": ctx.trace_id,
        }
        if hotl_action_id is not None:
            result["hotl_action_id"] = hotl_action_id
        return result
