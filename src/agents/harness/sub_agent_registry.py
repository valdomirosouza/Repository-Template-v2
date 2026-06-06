"""Pluggable registry of domain-specific sub-agent specializations.

Spec: specs/ai/sub-agent-specialization.md
ADR:  ADR-0032 (Sub-Agent Specialization Registry)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.observability.logger import get_logger

logger = get_logger("harness.sub_agent_registry")

RiskLevel = Literal["low", "medium", "high", "critical"]


@dataclass
class AgentConfig:
    """Configuration for a registered sub-agent specialization.

    Spec: specs/ai/sub-agent-specialization.md §2
    """

    name: str
    role: str
    system_prompt_template: str
    tool_set: list[str]
    risk_level: RiskLevel
    description: str = ""
    max_iterations: int = 3
    require_hitl: bool = True


class SubAgentRegistry:
    """Registry of domain-specific sub-agent specializations.

    Spec: specs/ai/sub-agent-specialization.md §3
    Thread-safety: mutations (register/unregister) are not concurrent-safe.
    This registry is populated at startup and read-only at runtime.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentConfig] = {}

    def register(self, name: str, config: AgentConfig) -> None:
        """Register a specialization. Raises ValueError on duplicate name."""
        if name in self._agents:
            raise ValueError(
                f"Sub-agent '{name}' is already registered. "
                "Unregister it first or use a different name."
            )
        if name != config.name:
            raise ValueError(f"Registry key '{name}' must match config.name '{config.name}'.")
        self._agents[name] = config
        logger.info("sub_agent_registered", name=name, risk_level=config.risk_level)

    def get(self, name: str) -> AgentConfig:
        """Return config for a registered specialization. Raises KeyError if not found."""
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(
                f"Sub-agent '{name}' is not registered. Available: {sorted(self._agents)}"
            ) from exc

    def list_by_risk_level(self, level: RiskLevel) -> list[AgentConfig]:
        """Return all specializations with the given risk level."""
        return [c for c in self._agents.values() if c.risk_level == level]

    def all(self) -> list[AgentConfig]:
        """Return all registered specializations."""
        return list(self._agents.values())

    def unregister(self, name: str) -> None:
        """Remove a specialization. Intended for tests only."""
        self._agents.pop(name, None)

    def __len__(self) -> int:
        return len(self._agents)


# ── Built-in specializations (registered at module import) ──────────────────
# Spec: specs/ai/sub-agent-specialization.md §4

_SECURITY_REVIEWER = AgentConfig(
    name="security-reviewer",
    role="Security Reviewer",
    description=(
        "Reviews code diffs for OWASP Top 10 and OWASP LLM Top 10 violations. "
        "Outputs structured findings: {tool, severity, file, line, cwe, remediation}."
    ),
    system_prompt_template=(
        "You are a security reviewer. Analyse the following code diff for vulnerabilities "
        "matching OWASP Top 10 (web) and OWASP LLM Top 10 (AI). "
        "For each finding output JSON: "
        '{"severity": "critical|high|medium|low", "file": "...", "line": N, '
        '"cwe": "CWE-NNN", "description": "...", "remediation": "..."}. '
        "Task: {{task}}"
    ),
    tool_set=["read_file", "grep", "gh_pr_diff"],
    risk_level="high",
    max_iterations=1,
    require_hitl=True,
)

_DOCUMENT_GENERATOR = AgentConfig(
    name="document-generator",
    role="Document Generator",
    description=(
        "Generates ADRs, runbooks, and spec drafts from structured input. "
        "Read-only — no code writes."
    ),
    system_prompt_template=(
        "You are a technical writer. Generate a well-structured Markdown document "
        "following the repository conventions in CLAUDE.md. "
        "Task: {{task}}"
    ),
    tool_set=["read_file", "grep"],
    risk_level="low",
    max_iterations=2,
    require_hitl=False,
)

# Module-level singleton — importers receive the same pre-populated instance.
default_registry = SubAgentRegistry()
default_registry.register("security-reviewer", _SECURITY_REVIEWER)
default_registry.register("document-generator", _DOCUMENT_GENERATOR)
