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
from pathlib import Path
from typing import Any

from src.observability.logger import get_logger
from src.shared.config import settings

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


class ExecutionMode(StrEnum):
    DIRECT = "direct"  # executed in-process via a Python function call
    SANDBOX = "sandbox"  # MUST be routed through SandboxExecutor (ADR-0016, ZT2)


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
    # execution_mode=SANDBOX means the orchestrator MUST route via SandboxExecutor.
    # Unregistered or DIRECT tools may execute in-process (subject to HITL gating).
    execution_mode: ExecutionMode = ExecutionMode.DIRECT
    adr_reference: str = ""
    endpoint_schema: dict[str, Any] = field(default_factory=dict)
    # ── HOTL reversibility metadata (ADR-0055) ──────────────────────────────────
    # Defaults are conservative (fail-closed): an unspecified tool is treated as
    # non-reversible and not eligible for autonomous HOTL execution.
    reversible: bool = False
    compensating_action: str | None = None
    max_hotl_risk_score: float = 0.0  # 0.0 = never auto-executes under HOTL
    allowed_autonomy_levels: tuple[str, ...] = ()
    requires_dual_approval: bool = False


# Fields the HOTL model requires every production tool to declare explicitly.
REVERSIBILITY_FIELDS: tuple[str, ...] = (
    "reversible",
    "compensating_action",
    "max_hotl_risk_score",
    "allowed_autonomy_levels",
)


class UnregisteredToolError(Exception):
    """Raised when an agent attempts to invoke a tool not in the registry."""


class ToolCatalogError(Exception):
    """Raised when the tool catalog (tools.yaml) fails schema validation at startup."""


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

    def is_registered(self, name: str) -> bool:
        """Return True if the (normalized) tool name is in the registry."""
        return self._normalize(name) in self._tools

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
        return autonomy_level in _permit_map.get(str(tool.risk_level), set())

    def list_by_risk(self, risk_level: str) -> list[ToolDefinition]:
        """Return all tools matching the given risk level."""
        return [t for t in self._tools.values() if str(t.risk_level) == risk_level]

    def all(self) -> list[ToolDefinition]:
        """Return all registered tools."""
        return list(self._tools.values())

    def assert_registered(self, name: str) -> ToolDefinition:
        """Return the tool or raise UnregisteredToolError (for use at orchestrator level)."""
        try:
            return self.get(name)
        except KeyError as exc:
            raise UnregisteredToolError(
                f"Agent attempted to invoke unregistered tool '{name}'. "
                "Register it in infrastructure/agent-tools/tools.yaml first."
            ) from exc

    def is_sandbox_required(self, name: str) -> bool:
        """Return True if the tool's execution_mode is SANDBOX.

        Accepts both hyphenated ('execute-code') and underscored ('execute_code') forms.
        Returns False for unregistered tools (the caller should also check registration).
        """
        normalized = self._normalize(name)
        try:
            tool = self.get(normalized)
            return tool.execution_mode == ExecutionMode.SANDBOX
        except KeyError:
            return False

    def is_reversible(self, name: str) -> bool:
        """Return True if the tool declares itself reversible. False if unregistered."""
        try:
            return self.get(self._normalize(name)).reversible
        except KeyError:
            return False

    def compensating_action(self, name: str) -> str | None:
        """Return the tool's compensating action name, or None."""
        try:
            return self.get(self._normalize(name)).compensating_action
        except KeyError:
            return None

    def max_hotl_risk_score(self, name: str) -> float:
        """Return the tool's max risk score eligible for autonomous HOTL. 0.0 if unknown."""
        try:
            return self.get(self._normalize(name)).max_hotl_risk_score
        except KeyError:
            return 0.0

    def requires_dual_approval(self, name: str) -> bool:
        """Return True if the tool requires dual approval. False if unregistered."""
        try:
            return self.get(self._normalize(name)).requires_dual_approval
        except KeyError:
            return False

    @staticmethod
    def _normalize(name: str) -> str:
        """Normalize action_type names: underscores → hyphens for registry lookup."""
        return name.replace("_", "-")


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
            reversible=False,
            compensating_action=None,
            max_hotl_risk_score=0.0,
            allowed_autonomy_levels=(),
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
            reversible=True,  # a read has no side effect
            compensating_action=None,
            max_hotl_risk_score=0.3,
            allowed_autonomy_levels=("low-risk", "medium-risk", "full"),
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
            reversible=True,
            compensating_action="restore-db-record",
            max_hotl_risk_score=0.0,  # routed via HITL (requires_hitl)
            allowed_autonomy_levels=("medium-risk", "full"),
        )
    )
    # ZT2: Code execution MUST always be routed through SandboxExecutor (ADR-0047, ADR-0016).
    registry.register(
        ToolDefinition(
            name="execute-code",
            description="Execute AI-generated Python code in an isolated Docker sandbox",
            version="1.0",
            risk_level=ToolRiskLevel.HIGH,
            pii_access=[],
            requires_hitl=True,
            execution_mode=ExecutionMode.SANDBOX,
            rate_limit_per_minute=2,
            rate_limit_per_hour=10,
            owner_team="platform",
            adr_reference="ADR-0047",
            reversible=False,
            compensating_action=None,
            max_hotl_risk_score=0.0,
            allowed_autonomy_levels=(),
            requires_dual_approval=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="send-external-request",
            description="Send an HTTP request to a registered external endpoint",
            version="1.0",
            risk_level=ToolRiskLevel.HIGH,
            pii_access=[PIILevel.L1, PIILevel.L2],
            requires_hitl=True,
            execution_mode=ExecutionMode.DIRECT,
            rate_limit_per_minute=5,
            rate_limit_per_hour=50,
            owner_team="integrations",
            adr_reference="ADR-0048",
            reversible=False,
            compensating_action=None,
            max_hotl_risk_score=0.0,
            allowed_autonomy_levels=(),
        )
    )
    return registry


# ── tools.yaml loading + startup validation (ADR-0055) ────────────────────────

_TOOLS_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "agent-tools" / "tools.yaml"
)


def _tool_from_yaml_entry(entry: dict[str, Any], *, strict: bool) -> ToolDefinition:
    """Build a ToolDefinition from a tools.yaml entry.

    When ``strict`` (production), every reversibility field MUST be present, or a
    ToolCatalogError is raised. In non-production, missing fields fall back to the
    conservative dataclass defaults.
    """
    name = entry.get("name", "<unnamed>")
    if strict:
        missing = [f for f in REVERSIBILITY_FIELDS if f not in entry]
        if missing:
            raise ToolCatalogError(
                f"tool '{name}' is missing required reversibility fields {missing}. "
                "Every production tool must declare reversibility metadata (ADR-0055)."
            )

    return ToolDefinition(
        name=name,
        description=entry.get("description", ""),
        version=str(entry.get("version", "1.0")),
        risk_level=ToolRiskLevel(entry["risk_level"]),
        pii_access=[PIILevel(p) for p in entry.get("pii_access", [])],
        requires_hitl=bool(entry.get("requires_hitl", True)),
        rate_limit_per_minute=int(entry.get("rate_limit_per_minute", 0)),
        rate_limit_per_hour=int(entry.get("rate_limit_per_hour", 0)),
        owner_team=entry.get("owner_team", "unknown"),
        execution_mode=ExecutionMode(entry.get("execution_mode", "direct")),
        adr_reference=entry.get("adr_reference", ""),
        reversible=bool(entry.get("reversible", False)),
        compensating_action=entry.get("compensating_action"),
        max_hotl_risk_score=float(entry.get("max_hotl_risk_score", 0.0)),
        allowed_autonomy_levels=tuple(entry.get("allowed_autonomy_levels", ()) or ()),
        requires_dual_approval=bool(entry.get("requires_dual_approval", False)),
    )


def load_tools_from_yaml(path: Path, *, strict: bool) -> ToolRegistry:
    """Load and validate the tool catalog from a tools.yaml file.

    Raises ToolCatalogError if the file is malformed or (when ``strict``) any tool
    is missing required reversibility metadata.
    """
    import yaml  # type: ignore[import-untyped]

    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ToolCatalogError(f"failed to read tool catalog {path}: {exc}") from exc

    if not isinstance(raw, dict) or "tools" not in raw:
        raise ToolCatalogError(f"tool catalog {path} must contain a top-level 'tools' list")

    registry = ToolRegistry()
    for entry in raw["tools"]:
        registry.register(_tool_from_yaml_entry(entry, strict=strict))
    return registry


def _build_default_registry() -> ToolRegistry:
    """Build the module-level registry, preferring the canonical tools.yaml.

    In production a missing/invalid catalog or missing reversibility metadata is a
    hard failure (ToolCatalogError). In non-production we fall back to the built-in
    starter catalog so local dev and tests run without the file.
    """
    strict = settings.app_env == "production"
    if _TOOLS_YAML_PATH.exists():
        return load_tools_from_yaml(_TOOLS_YAML_PATH, strict=strict)
    if strict:
        raise ToolCatalogError(
            f"tool catalog not found at {_TOOLS_YAML_PATH} — required in production"
        )
    return _load_default_registry()


# Module-level singleton — can be replaced in tests via dependency injection.
default_tool_registry = _build_default_registry()
