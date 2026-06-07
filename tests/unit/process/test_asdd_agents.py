"""Consistency tests for the Claude Code delivery-agent system (ADR-0058).

Validates the orchestrator + 15 phase subagents in .claude/agents/:
frontmatter, real Claude Code tool names, full phase coverage (0–14), handoff
contract usage, and the human-gate / no-autonomous-real-world-effects governance.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[3]
_AGENTS = _ROOT / ".claude" / "agents"

# Real Claude Code tool names that may appear in subagent frontmatter.
_VALID_TOOLS = {
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Grep",
    "Glob",
    "Agent",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
}

# Phases whose handoff must cross a mandatory human-approval gate.
_HUMAN_GATE_PHASES = {2, 4, 7, 9, 10, 11, 12, 13, 14}


def _agent_files() -> list[Path]:
    return sorted(p for p in _AGENTS.glob("asdd-*.md") if p.name != "README.md")


def _parse(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert m, f"{path.name}: missing/invalid frontmatter"
    return yaml.safe_load(m.group(1)), m.group(2)


def _phase_files() -> dict[int, Path]:
    out: dict[int, Path] = {}
    for f in _agent_files():
        m = re.match(r"asdd-phase-(\d+)-", f.name)
        if m:
            out[int(m.group(1))] = f
    return out


def test_sixteen_agents_exist():
    files = _agent_files()
    assert len(files) == 16, f"expected orchestrator + 15 phase agents, got {len(files)}"
    assert (_AGENTS / "asdd-orchestrator.md").exists()


def test_every_agent_has_frontmatter_fields():
    for f in _agent_files():
        fm, body = _parse(f)
        assert fm.get("name"), f"{f.name}: no name"
        assert fm.get("description"), f"{f.name}: no description"
        assert fm.get("tools"), f"{f.name}: no tools"
        assert body.strip(), f"{f.name}: empty system prompt body"


def test_tools_are_valid_claude_code_tools():
    for f in _agent_files():
        fm, _ = _parse(f)
        tools = [t.strip() for t in fm["tools"].split(",")]
        bad = [t for t in tools if t not in _VALID_TOOLS]
        assert not bad, f"{f.name}: invalid tools {bad}"


def test_agent_name_matches_filename():
    for f in _agent_files():
        fm, _ = _parse(f)
        assert fm["name"] == f.stem, f"{f.name}: name '{fm['name']}' != filename stem"


def test_phases_0_to_14_fully_covered():
    assert sorted(_phase_files()) == list(range(0, 15))


def test_each_phase_uses_handoff_helper():
    for n, f in _phase_files().items():
        _, body = _parse(f)
        assert "asdd_state.py append-handoff" in body, f"phase {n}: no handoff via asdd_state.py"
        assert "blocked" in body, f"phase {n}: no blocked rule"


def test_human_gate_phases_declare_gate():
    for n, f in _phase_files().items():
        _, body = _parse(f)
        if n in _HUMAN_GATE_PHASES:
            assert "--human-gate" in body or "human_gate" in body, (
                f"phase {n} is a mandatory human gate but does not declare one"
            )


def test_production_phase_is_prepare_only():
    _, body = _parse(_phase_files()[13])
    low = body.lower()
    assert "do not" in low or "not deploy" in low or "human-executed" in low
    # The production agent must not carry write/deploy tooling beyond read + bash.
    fm, _ = _parse(_phase_files()[13])
    tools = {t.strip() for t in fm["tools"].split(",")}
    assert tools <= {"Read", "Bash", "Grep", "Glob"}, f"phase 13 has write/effect tools: {tools}"


def test_orchestrator_manages_all_phases():
    fm, body = _parse(_AGENTS / "asdd-orchestrator.md")
    assert "Agent" in fm["tools"], "orchestrator needs the Agent tool to invoke subagents"
    for n in range(0, 15):
        # each phase agent name appears in the orchestrator's managed list
        assert re.search(rf"asdd-phase-{n}-", body), f"orchestrator does not reference phase {n}"


def test_ai_safety_phase_is_conditional():
    _, body = _parse(_phase_files()[10])
    assert "conditional" in body.lower() or "N/A" in body
