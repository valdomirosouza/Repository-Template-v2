"""Governed tool registry — declares every tool an agent may invoke.

Spec:  specs/ai/tool-registry.md
ADR:   ADR-0039
Issue: #16

Unregistered tool calls are blocked at the orchestrator level.
The canonical tool catalog is loaded from infrastructure/agent-tools/tools.yaml at startup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.observability.logger import get_logger

logger = get_logger(__name__)


class ToolRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PIILevel(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    version: str
    risk_level: ToolRiskLevel
    pii_access: list[PIILevel]
    requires_hitl: bool
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    owner_team: str
    adr_reference: str = ""
    endpoint_schema: dict[str, Any] = field(default_factory=dict)


class UnregisteredToolError(Exception):
    """Raised when an agent attempts to invoke a tool not in the registry."""


class ToolRegistry:
    """Singleton registry of all declared agent tools.

    Tools must be registered at startup (loaded from tools.yaml).
    Runtime calls to register() are permitted only in tests.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    # ── Write operations ──────────────────────────────────────────────────────

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool. Raises ValueError if the name is already registered."""
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                "Unregister it first (testing only) or bump its version."
            )
        self._tools[tool.name] = tool
        logger.info("tool.registered", tool_name=tool.name, version=tool.version)

    def unregister(self, name: str) -> None:
        """Remove a tool — for testing only. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        del self._tools[name]

    # ── Read operations ───────────────────────────────────────────────────────

    def get(self, name: str) -> ToolDefinition:
        """Return a ToolDefinition. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name]

    def check_permission(self, name: str, autonomy_level: str) -> bool:
        """Return True if the tool may be invoked at the given autonomy level.

        Tools with requires_hitl=True always return True — HITL will gate the action.
        For others, the autonomy level must meet the tool's risk level requirement.
        """
        tool = self.get(name)
        if tool.requires_hitl:
            return True  # HITL gateway enforces the gate

        _permit_map: dict[str, set[str]] = {
            "low": {"low-risk", "medium-risk", "full"},
            "medium": {"medium-risk", "full"},
            "high": {"full"},
        }
        return autonomy_level in _permit_map.get(tool.risk_level.value, set())

    def list_by_risk(self, risk_level: str) -> list[ToolDefinition]:
        """Return all tools matching the given risk level."""
        return [t for t in self._tools.values() if t.risk_level.value == risk_level]

    def all(self) -> list[ToolDefinition]:
        """Return all registered tools."""
        return list(self._tools.values())

    def assert_registered(self, name: str) -> ToolDefinition:
        """Return the tool or raise UnregisteredToolError (for use at orchestrator level)."""
        try:
            return self.get(name)
        except KeyError:
            raise UnregisteredToolError(
                f"Agent attempted to invoke unregistered tool '{name}'. "
                "Register it in infrastructure/agent-tools/tools.yaml first."
            )


def _load_default_registry() -> ToolRegistry:
    """Build the default registry from the built-in starter catalog."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="send-email",
            description="Send an email notification to one or more recipients",
            version="1.0",
            risk_level=ToolRiskLevel.HIGH,
            pii_access=[PIILevel.L1, PIILevel.L2],
            requires_hitl=True,
            rate_limit_per_minute=2,
            rate_limit_per_hour=20,
            owner_team="platform",
            adr_reference="ADR-0011",
        )
    )
    registry.register(
        ToolDefinition(
            name="read-db-record",
            description="Read a single record from the database by ID",
            version="1.0",
            risk_level=ToolRiskLevel.LOW,
            pii_access=[PIILevel.L3],
            requires_hitl=False,
            rate_limit_per_minute=60,
            rate_limit_per_hour=1000,
            owner_team="platform",
            adr_reference="ADR-0039",
        )
    )
    registry.register(
        ToolDefinition(
            name="write-db-record",
            description="Create or update a record in the database",
            version="1.0",
            risk_level=ToolRiskLevel.MEDIUM,
            pii_access=[PIILevel.L2, PIILevel.L3],
            requires_hitl=True,
            rate_limit_per_minute=10,
            rate_limit_per_hour=100,
            owner_team="platform",
            adr_reference="ADR-0039",
        )
    )
    return registry


# Module-level singleton — can be replaced in tests via dependency injection.
default_tool_registry = _load_default_registry()
