"""Adaptive runtime policy gateway for agent action decisions.

Enforces a declarative policy (loaded from infrastructure/agent-policies/policies.yaml)
at the act layer, BEFORE the HITL gateway. Policies can be updated without a code deploy
by reloading the YAML file.

Policy decisions: ALLOW | REQUIRE_HITL | BLOCK

BLOCK stops the action immediately (raises RuntimePolicyError).
REQUIRE_HITL forces HITL routing regardless of the current autonomy level or risk_score.
ALLOW lets the action proceed normally through the existing HITL/HOTL logic.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 3 (BM2)
ADR:  ADR-0049
Issue: #34
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.observability.logger import get_logger
from src.observability.metrics import AGENT_POLICY_DECISION_COUNTER

logger = get_logger("runtime_policy_gateway")


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_HITL = "REQUIRE_HITL"
    BLOCK = "BLOCK"


class RuntimePolicyError(Exception):
    """Raised when a policy decision is BLOCK."""


@dataclass(frozen=True)
class PolicyCondition:
    """Matches a subset of action contexts."""

    task_type_pattern: str = ""  # glob-style prefix match (* = wildcard)
    proposed_action_type: str = ""  # exact match on action_type
    method: tuple[str, ...] = ()  # HTTP methods (for external requests)
    pii_level_gte: str = ""  # match if action touches PII at this level or higher


@dataclass(frozen=True)
class Policy:
    name: str
    condition: PolicyCondition
    decision: PolicyDecision
    reason: str = ""


@dataclass
class RequestContext:
    """Minimal context passed to the policy gateway for evaluation."""

    task_type: str = ""
    proposed_action_type: str = ""
    method: str = ""
    pii_level: str = ""  # e.g. "L1", "L2", "L3", "L4"


_PII_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}


class RuntimePolicyGateway:
    """Evaluates agent actions against a loaded policy set.

    Policies are evaluated in order; the first matching policy wins.
    If no policy matches, the default is ALLOW.

    Usage::

        policy_path = Path("infrastructure/agent-policies/policies.yaml")
        gateway = RuntimePolicyGateway.from_yaml(policy_path)
        decision = gateway.evaluate("execute-code", context)
        if decision == PolicyDecision.BLOCK:
            raise RuntimePolicyError(...)
    """

    def __init__(self, policies: list[Policy]) -> None:
        self._policies = policies

    @classmethod
    def from_yaml(cls, path: Path) -> RuntimePolicyGateway:
        """Load policies from a YAML file."""
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        policies = [cls._parse_policy(p) for p in raw.get("policies", [])]
        logger.info("runtime_policy_gateway.loaded", path=str(path), count=len(policies))
        return cls(policies)

    @classmethod
    def from_list(cls, policies: list[Policy]) -> RuntimePolicyGateway:
        """Build a gateway from a pre-constructed policy list (useful for tests)."""
        return cls(policies)

    @staticmethod
    def _parse_policy(raw: dict[str, Any]) -> Policy:
        cond_raw = raw.get("condition", {})
        condition = PolicyCondition(
            task_type_pattern=cond_raw.get("task_type_pattern", ""),
            proposed_action_type=cond_raw.get("proposed_action_type", ""),
            method=tuple(cond_raw.get("method", [])),
            pii_level_gte=cond_raw.get("pii_level_gte", ""),
        )
        return Policy(
            name=raw.get("name", "unnamed"),
            condition=condition,
            decision=PolicyDecision(raw.get("decision", "ALLOW")),
            reason=raw.get("reason", ""),
        )

    def evaluate(self, action_type: str, context: RequestContext) -> PolicyDecision:
        """Return the first matching policy decision, or ALLOW if none match."""
        for policy in self._policies:
            if self._matches(policy.condition, action_type, context):
                decision = policy.decision
                AGENT_POLICY_DECISION_COUNTER.labels(
                    policy_name=policy.name,
                    decision=decision.value,
                ).inc()
                log_fn = logger.warning if decision == PolicyDecision.BLOCK else logger.info
                log_fn(
                    "runtime_policy_gateway.decision",
                    policy=policy.name,
                    decision=decision.value,
                    action_type=action_type,
                    task_type=context.task_type,
                    reason=policy.reason,
                )
                return decision

        AGENT_POLICY_DECISION_COUNTER.labels(
            policy_name="default",
            decision=PolicyDecision.ALLOW.value,
        ).inc()
        return PolicyDecision.ALLOW

    def evaluate_or_raise(self, action_type: str, context: RequestContext) -> PolicyDecision:
        """Like evaluate(), but raises RuntimePolicyError on BLOCK decisions."""
        decision = self.evaluate(action_type, context)
        if decision == PolicyDecision.BLOCK:
            matching = self._find_matching_policy(action_type, context)
            reason = matching.reason if matching else "policy blocked this action"
            raise RuntimePolicyError(
                f"Action '{action_type}' was BLOCKED by runtime policy. Reason: {reason}"
            )
        return decision

    def reload(self, path: Path) -> None:
        """Hot-reload policies from disk without recreating the gateway instance."""
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self._policies = [self._parse_policy(p) for p in raw.get("policies", [])]
        logger.info("runtime_policy_gateway.reloaded", path=str(path), count=len(self._policies))

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _matches(cond: PolicyCondition, action_type: str, ctx: RequestContext) -> bool:
        """Return True if all non-empty condition fields match the request context."""
        if cond.task_type_pattern:
            pattern = cond.task_type_pattern.replace("*", ".*")
            if not re.fullmatch(pattern, ctx.task_type):
                return False

        if cond.proposed_action_type:
            if cond.proposed_action_type != action_type:
                return False

        if cond.method:
            if ctx.method.upper() not in [m.upper() for m in cond.method]:
                return False

        if cond.pii_level_gte:
            ctx_level = _PII_ORDER.get(ctx.pii_level, 99)
            threshold = _PII_ORDER.get(cond.pii_level_gte, 99)
            if ctx_level > threshold:  # lower number = more sensitive
                return False

        return True

    def _find_matching_policy(self, action_type: str, ctx: RequestContext) -> Policy | None:
        for p in self._policies:
            if self._matches(p.condition, action_type, ctx):
                return p
        return None
