#!/usr/bin/env python3
"""Agentic Maturity Self-Assessment — evaluates this repository against the four
Gartner agentic maturity levels and emits a structured report.

Spec:  specs/ai/agentic-maturity-assessment.md
ADR:   ADR-0040
Issue: #17

Run via:  make agentic-maturity-check
          python scripts/agentic_maturity_check.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# ── Criterion helpers ─────────────────────────────────────────────────────────


def _file_exists(rel: str) -> bool:
    return (REPO_ROOT / rel).exists()


def _yaml_has_variant(rel: str, variant: str) -> bool:
    p = REPO_ROOT / rel
    if not p.exists():
        return False
    return variant in p.read_text()


def _yaml_tool_count(rel: str) -> int:
    p = REPO_ROOT / rel
    if not p.exists():
        return 0
    return p.read_text().count("- name:")


def _all_autonomy_flags_off() -> bool:
    flag_dir = REPO_ROOT / "infrastructure/feature-flags/flags"
    for flag_file in flag_dir.glob("autonomous-mode*.yaml"):
        content = flag_file.read_text()
        if 'defaultVariant: "on"' in content or "defaultVariant: true" in content:
            return False
    return True


# ── Criterion dataclass ───────────────────────────────────────────────────────


@dataclass
class Criterion:
    description: str
    met: bool
    detail: str = ""


@dataclass
class LevelResult:
    level: int
    name: str
    criteria: list[Criterion] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.met for c in self.criteria)

    @property
    def missing(self) -> list[Criterion]:
        return [c for c in self.criteria if not c.met]


# ── Level definitions ─────────────────────────────────────────────────────────


def check_level_1() -> LevelResult:
    """Assistance — agent as smart conversational tool."""
    result = LevelResult(1, "ASSISTANCE")
    result.criteria = [
        Criterion(
            "src/agents/ present (agents module exists)",
            _file_exists("src/agents/__init__.py"),
        ),
        Criterion(
            "HITL gateway present (src/agents/hitl_gateway.py)",
            _file_exists("src/agents/hitl_gateway.py"),
        ),
        Criterion(
            "CLAUDE.md present (behavioral contract)",
            _file_exists("CLAUDE.md"),
        ),
    ]
    return result


def check_level_2() -> LevelResult:
    """Automation — discrete workflows; humans approve each step."""
    tool_count = _yaml_tool_count("infrastructure/agent-tools/tools.yaml")
    result = LevelResult(2, "AUTOMATION")
    result.criteria = [
        Criterion(
            "HITL gateway active (src/agents/hitl_gateway.py)",
            _file_exists("src/agents/hitl_gateway.py"),
        ),
        Criterion(
            f"Tool registry has ≥ 1 tool (found: {tool_count})",
            tool_count >= 1,
            detail=f"infrastructure/agent-tools/tools.yaml — {tool_count} tools",
        ),
        Criterion(
            "Audit logger present (src/guardrails/audit_logger.py)",
            _file_exists("src/guardrails/audit_logger.py"),
        ),
        Criterion(
            "Unit tests present (tests/unit/)",
            _file_exists("tests/unit"),
        ),
    ]
    return result


def check_level_3() -> LevelResult:
    """Augmentation — multi-step workflows by agent clusters with HITL oversight."""
    result = LevelResult(3, "AUGMENTATION")
    result.criteria = [
        Criterion(
            "Planner→Generator→Evaluator harness present (src/agents/harness/)",
            _file_exists("src/agents/harness/planner.py")
            and _file_exists("src/agents/harness/evaluator.py"),
        ),
        Criterion(
            "FeedbackLearner present (src/agents/feedback_learner.py)",
            _file_exists("src/agents/feedback_learner.py"),
        ),
        Criterion(
            "learning-mode flag present (infrastructure/feature-flags/flags/learning-mode.yaml)",
            _file_exists("infrastructure/feature-flags/flags/learning-mode.yaml"),
        ),
        Criterion(
            "SubAgentRegistry present (src/agents/harness/sub_agent_registry.py)",
            _file_exists("src/agents/harness/sub_agent_registry.py"),
        ),
        Criterion(
            "SessionCheckpoint present (src/agents/harness/session_checkpoint.py)",
            _file_exists("src/agents/harness/session_checkpoint.py"),
        ),
    ]
    return result


def check_level_4() -> LevelResult:
    """Autonomy — long-horizon goals, context graphs, full governance prerequisites."""
    active = _yaml_has_variant("infrastructure/feature-flags/flags/learning-mode.yaml", '"active"')
    tier_ready = _yaml_has_variant(
        "infrastructure/feature-flags/flags/autonomy-tier-ready.yaml", '"true"'
    )
    result = LevelResult(4, "AUTONOMY")
    result.criteria = [
        Criterion(
            "learning-mode flag set to active",
            active,
            detail="Set defaultVariant to 'active' in learning-mode.yaml after ADR-0038 sign-off",
        ),
        Criterion(
            "Context graph present (src/agents/context_graph.py)",
            _file_exists("src/agents/context_graph.py"),
            detail="Implement context graph per specs/ai/context-graph.md (ADR-0041)",
        ),
        Criterion(
            "autonomy-tier-ready flag present and enabled",
            _file_exists("infrastructure/feature-flags/flags/autonomy-tier-ready.yaml")
            and tier_ready,
            detail="Requires governance council sign-off (ADR-0037, ADR-0041)",
        ),
    ]
    return result


# ── Report ────────────────────────────────────────────────────────────────────

_GARTNER_COVERAGE = {1: 40, 2: 60, 3: 80, 4: 92}


def run() -> int:
    levels = [check_level_1(), check_level_2(), check_level_3(), check_level_4()]

    current_level = 0
    for lvl in levels:
        if lvl.passed:
            current_level = lvl.level
        else:
            break

    level_names = {0: "NONE", 1: "ASSISTANCE", 2: "AUTOMATION", 3: "AUGMENTATION", 4: "AUTONOMY"}
    current_name = level_names[current_level]
    coverage = _GARTNER_COVERAGE.get(current_level, 0)

    print("=" * 50)
    print("Agentic Maturity Assessment")
    print("=" * 50)
    print(f"Date:       {date.today()}")
    print("Repository: Repository-Template-v2")
    print()
    print(f"Current maturity level: {current_name} (Level {current_level})")
    print(f"Gartner compliance coverage: ~{coverage}%")
    print()

    for lvl in levels:
        icon = "✅" if lvl.passed else "⚠️ "
        print(f"{icon} Level {lvl.level} — {lvl.name}: {'PASS' if lvl.passed else 'PARTIAL'}")
        if not lvl.passed:
            print(f"\n  Missing for {lvl.name} (Level {lvl.level}):")
            for c in lvl.missing:
                print(f"    ✗ {c.description}")
                if c.detail:
                    print(f"      → {c.detail}")
            print()

    next_level = current_level + 1
    if next_level <= 4:
        next_name = level_names[next_level]
        next_target = _GARTNER_COVERAGE.get(next_level, 92)
        print(f"Next target: {next_name} (Level {next_level}) → ~{next_target}% Gartner coverage")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(run())
