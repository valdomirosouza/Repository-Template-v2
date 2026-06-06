"""Controlled tool executor — 10-step pre-execution enforcement sequence.

Enforces tool registry policy before any action reaches execution:

  1.  Normalize action name (lowercase, hyphens)
  2.  Assert tool is registered in the catalog
  3.  Validate parameters against tool schema (if defined)
  4.  Check tool.requires_hitl — return HITL_REQUIRED if true
  5.  Check autonomy level permits the tool's risk level
  6.  Detect sandbox-required tools; block direct bypass attempts
  7.  Execute via SandboxExecutor (sandbox) or direct call (permitted)
  8.  Emit pre-execution audit record
  9.  Emit post-execution audit record
  10. Emit failure audit record if execution fails

This class is the single choke-point between the orchestrator's routing
decision and actual tool execution. All 10 steps are mandatory.

Spec: specs/ai/hitl-hotl.md §tool-registry-runtime
ADR:  ADR-0048 (zero-trust tool registry), ADR-0053
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from src.agents.tool_registry import ToolRegistry, UnregisteredToolError, default_tool_registry
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.shared.models import AuditEvent

logger = get_logger("tool_executor")


class ToolNotRegisteredError(ValueError):
    """Raised when the requested tool is not in the registry (step 2)."""


class ToolPermissionDeniedError(PermissionError):
    """Raised when the autonomy level does not permit the tool (step 5)."""


class ToolRateLimitExceededError(Exception):
    """Raised when a tool's per-minute or per-hour rate limit is exceeded (step 5b)."""


class SandboxBypassAttemptError(Exception):
    """Raised when a sandbox-required tool attempts direct execution (step 6)."""


@dataclass
class ToolExecutionResult:
    """Result returned by ToolExecutor.execute()."""

    action_type: str
    outcome: str  # EXECUTED | HITL_REQUIRED | BLOCKED | FAILED
    result: dict[str, Any] = field(default_factory=dict)
    hitl_required: bool = False
    sandbox_used: bool = False
    error: str | None = None


class ToolExecutor:
    """Enforces the 10-step tool registry policy before any action executes.

    Instantiate once per orchestrator and inject the same audit_logger.
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        registry: ToolRegistry | None = None,
        sandbox_executor: Any | None = None,
    ) -> None:
        self._audit = audit_logger
        self._registry = registry or default_tool_registry
        self._sandbox = sandbox_executor
        # Per-tool call timestamps for rate-limit enforcement (step 5b).
        self._call_log: dict[str, deque[float]] = defaultdict(deque)

    # ── Pre-flight helpers (used by the orchestrator routing decision) ──────────

    @staticmethod
    def _normalize_name(action_type: str) -> str:
        return action_type.lower().strip().replace("_", "-")

    def is_registered(self, action_type: str) -> bool:
        """Return True if the (normalized) action maps to a registered tool."""
        return self._registry.is_registered(self._normalize_name(action_type))

    def permits_autonomous(self, action_type: str, autonomy_level: str) -> bool:
        """Return True if the tool may execute autonomously at this autonomy level.

        Autonomous execution requires the tool to be registered, not flagged
        requires_hitl, and permitted for the given autonomy level. Anything else
        must fall back to HITL routing (decided by the orchestrator).
        """
        normalized = self._normalize_name(action_type)
        if not self._registry.is_registered(normalized):
            return False
        tool = self._registry.get(normalized)
        if tool.requires_hitl:
            return False
        return self._registry.check_permission(normalized, autonomy_level)

    async def execute(
        self,
        action_type: str,
        parameters: dict[str, Any],
        autonomy_level: str,
        agent_id: str,
        trace_id: str | None = None,
        hitl_approved: bool = False,
    ) -> ToolExecutionResult:
        """Run the 10-step enforcement sequence and execute if all checks pass.

        When ``hitl_approved`` is True the action has already cleared the HITL
        gateway, so step 4 (requires_hitl) and step 5 (autonomy permission) are
        treated as satisfied — a human reviewer is the highest authority and may
        approve actions above the current autonomy ceiling. Registry (step 2)
        and sandbox (step 6) enforcement are NEVER skipped, even after approval.
        """

        # Step 1: Normalize action name
        normalized = action_type.lower().strip().replace("_", "-")

        # Step 2: Assert tool is registered
        try:
            tool = self._registry.assert_registered(normalized)
        except (KeyError, ValueError, UnregisteredToolError) as exc:
            logger.error("tool_executor.unregistered", action_type=normalized, agent_id=agent_id)
            await self._audit.log_event(
                AuditEvent(
                    event_type="agent.action.blocked",
                    agent_id=agent_id,
                    action=normalized,
                    outcome="BLOCKED_UNREGISTERED",
                    risk_score=1.0,
                    metadata={"reason": "tool not in registry"},
                    trace_id=trace_id,
                )
            )
            raise ToolNotRegisteredError(
                f"Tool '{normalized}' is not registered in the tool catalog. "
                "Register it in infrastructure/agent-tools/tools.yaml before use."
            ) from exc

        # Step 3: Validate parameters against schema
        if tool.endpoint_schema:
            self._validate_schema(normalized, parameters, tool.endpoint_schema)

        # Step 4: Check requires_hitl — short-circuit; HITL gateway owns the rest.
        # Skipped when the action already cleared HITL (hitl_approved=True).
        if tool.requires_hitl and not hitl_approved:
            logger.info("tool_executor.hitl_required", action_type=normalized, agent_id=agent_id)
            return ToolExecutionResult(
                action_type=normalized,
                outcome="HITL_REQUIRED",
                hitl_required=True,
            )

        # Step 5: Check autonomy level permits this tool's risk level.
        # Skipped when a human reviewer already approved (hitl_approved=True).
        if not hitl_approved and not self._registry.check_permission(normalized, autonomy_level):
            logger.warning(
                "tool_executor.permission_denied",
                action_type=normalized,
                autonomy_level=autonomy_level,
                tool_risk=tool.risk_level,
                agent_id=agent_id,
            )
            await self._audit.log_event(
                AuditEvent(
                    event_type="agent.action.blocked",
                    agent_id=agent_id,
                    action=normalized,
                    outcome="BLOCKED_PERMISSION",
                    risk_score=1.0,
                    metadata={
                        "reason": "autonomy level insufficient for tool risk",
                        "autonomy_level": autonomy_level,
                        "tool_risk_level": tool.risk_level,
                        "owner_team": tool.owner_team,
                    },
                    trace_id=trace_id,
                )
            )
            raise ToolPermissionDeniedError(
                f"Autonomy level '{autonomy_level}' does not permit tool '{normalized}' "
                f"(requires risk_level ≤ {tool.risk_level})"
            )

        # Step 5b: Enforce per-tool rate limits before execution (never skipped —
        # rate limits protect downstream systems regardless of HITL approval).
        self._enforce_rate_limit(normalized, tool.rate_limit_per_minute, tool.rate_limit_per_hour)

        # Step 6: Detect sandbox-required tools; block direct bypass
        sandbox_required = self._registry.is_sandbox_required(normalized)
        if sandbox_required and self._sandbox is None:
            raise SandboxBypassAttemptError(
                f"Tool '{normalized}' requires SANDBOX execution mode but no "
                "SandboxExecutor is configured. Configure sandbox before use."
            )

        # Step 8: Emit pre-execution audit record
        await self._audit.log_event(
            AuditEvent(
                event_type="agent.action.executing",
                agent_id=agent_id,
                action=normalized,
                outcome="EXECUTING",
                risk_score=0.0,
                metadata={
                    "tool_name": normalized,
                    "execution_mode": str(tool.execution_mode),
                    "owner_team": tool.owner_team,
                    "sandbox_used": sandbox_required,
                    "autonomy_level": autonomy_level,
                },
                trace_id=trace_id,
            )
        )

        # Steps 6 + 7: Execute
        try:
            if sandbox_required and self._sandbox is not None:
                result: dict[str, Any] = await self._sandbox.execute(
                    action_type=normalized, parameters=parameters
                )
            else:
                # Direct execution — tool is registered, permitted, and non-sandbox
                result = {
                    "status": "executed",
                    "tool": normalized,
                    "autonomy_level": autonomy_level,
                }

            # Step 9: Post-execution audit
            await self._audit.log_event(
                AuditEvent(
                    event_type="agent.action.executed",
                    agent_id=agent_id,
                    action=normalized,
                    outcome="EXECUTED",
                    risk_score=0.0,
                    metadata={
                        "tool_name": normalized,
                        "execution_mode": str(tool.execution_mode),
                        "owner_team": tool.owner_team,
                        "sandbox_used": sandbox_required,
                    },
                    trace_id=trace_id,
                )
            )
            return ToolExecutionResult(
                action_type=normalized,
                outcome="EXECUTED",
                result=result,
                sandbox_used=sandbox_required,
            )

        except (
            ToolNotRegisteredError,
            ToolPermissionDeniedError,
            ToolRateLimitExceededError,
            SandboxBypassAttemptError,
        ):
            raise
        except Exception as exc:
            # Step 10: Failure audit
            await self._audit.log_event(
                AuditEvent(
                    event_type="agent.action.failed",
                    agent_id=agent_id,
                    action=normalized,
                    outcome="FAILED",
                    risk_score=0.0,
                    metadata={"error": str(exc), "tool_name": normalized},
                    trace_id=trace_id,
                )
            )
            return ToolExecutionResult(
                action_type=normalized,
                outcome="FAILED",
                error=str(exc),
            )

    def _enforce_rate_limit(self, name: str, per_minute: int, per_hour: int) -> None:
        """Sliding-window rate-limit enforcement per tool (step 5b).

        Records this call's timestamp and raises ToolRateLimitExceededError if
        the per-minute or per-hour limit would be exceeded. Limits of 0 or below
        are treated as unlimited.
        """
        now = time.monotonic()
        log = self._call_log[name]
        # Evict timestamps older than one hour.
        while log and now - log[0] > 3600:
            log.popleft()

        if per_hour and per_hour > 0:
            if len(log) >= per_hour:
                raise ToolRateLimitExceededError(
                    f"Tool '{name}' exceeded per-hour rate limit ({per_hour})"
                )
        if per_minute and per_minute > 0:
            recent = sum(1 for ts in log if now - ts <= 60)
            if recent >= per_minute:
                raise ToolRateLimitExceededError(
                    f"Tool '{name}' exceeded per-minute rate limit ({per_minute})"
                )
        log.append(now)

    @staticmethod
    def _validate_schema(
        action_type: str, parameters: dict[str, Any], schema: dict[str, Any]
    ) -> None:
        required = schema.get("required", [])
        missing = [f for f in required if f not in parameters]
        if missing:
            raise ValueError(f"Tool '{action_type}' missing required parameters: {missing}")
