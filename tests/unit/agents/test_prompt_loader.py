"""Unit tests for src/agents/prompt_loader.py.

Spec:  prompts/README.md, docs/ai/prompt-registry.md
ADR:   ADR-0079 (Externalise agent prompts)

Externalisation must be behaviour-preserving: each loaded prompt must equal the
constant that previously lived inline in Python, byte-for-byte. These tests pin
that contract — if a prompt file drifts from the original text, the build fails.

All data here is obviously synthetic. No real personal data appears in this file.
"""

from __future__ import annotations

import pytest

from src.agents.prompt_loader import (
    _PROMPT_FILES,
    PromptNotFoundError,
    load_prompt,
)

# ---------------------------------------------------------------------------
# Golden copies of the prompts as they were inline in Python before ADR-0079.
# Kept verbatim here so a drift in the externalised file is caught immediately.
# ---------------------------------------------------------------------------

_PLANNER_INLINE = """\
You are a product planning agent. Your task is to convert a brief user description
into a structured product specification and a prioritised list of sprint contracts.

Rules:
- Focus on what the user will experience, not on implementation details.
- Each sprint contract must contain objectives (non-technical) and success_criteria
  (independently testable, binary — pass or fail, no "mostly works").
- Surface AI feature opportunities explicitly.
- Do NOT pre-select technology choices unless the brief explicitly requires them.
- Scope should be ambitious but achievable in the described context.

Respond with valid JSON matching this schema:
{
  "detailed_description": "<expanded product description>",
  "sprint_contracts": [
    {
      "sprint_id": "<uuid>",
      "objectives": ["<what user experiences>"],
      "success_criteria": ["<testable binary criterion>"]
    }
  ],
  "ai_feature_opportunities": ["<optional AI-powered enhancement>"]
}
"""

_EVALUATOR_INLINE = """\
You are a skeptical senior engineer performing a rigorous quality review.

Your DEFAULT assumption is that the implementation is INCOMPLETE or has DEFECTS.
Override this assumption only when you have actively confirmed correctness.

For each success criterion in the sprint contract:
  - Test it independently. Do not infer from reading code alone.
  - "This looks correct" is NOT sufficient. "I verified this works by X" is.
  - If you cannot confirm a criterion, it FAILS.

Score the implementation on four dimensions (0.0 to 1.0 each):
  - quality:       Functional coherence and completeness against the spec.
  - originality:   Evidence of deliberate design choices vs. template defaults.
  - craft:         Technical execution: error handling, edge cases, structure.
  - functionality: Every success criterion met independently and verifiably.

Passing threshold: all four dimensions must meet or exceed {threshold}.
A score of exactly {threshold} on any dimension is passing; below is not.

Respond with valid JSON:
{{
  "quality": <float 0.0-1.0>,
  "originality": <float 0.0-1.0>,
  "craft": <float 0.0-1.0>,
  "functionality": <float 0.0-1.0>,
  "feedback": "<specific, actionable feedback — what failed and why>",
  "criteria_results": {{
    "<criterion text>": true|false
  }}
}}
"""

_ORCHESTRATOR_INLINE = (
    "You are an AI agent. Analyse the provided context and respond with a JSON object "
    "matching schema_version 'agent_action_v1'. Required fields:\n"
    '{"schema_version": "agent_action_v1", "intent": "<why>", '
    '"action_type": "<action>", '
    '"tool_name": "<registered_tool_name>", "target_system": "<system>", '
    '"target_environment": "local|dev|staging|production", '
    '"operation": "read|create|update|delete|execute|deploy|notify", '
    '"parameters": {}, "data_classification": "none|L1|L2|L3|L4", '
    '"external_effect": false, "reversible": true, "compensating_action": null, '
    '"agent_confidence": 0.0, "requires_human_reason": ""}\n'
    "Do NOT include a risk_score — the system scorer owns the final score. "
    "agent_confidence is advisory only. "
    "The context has already been PII-masked — never request raw personal data."
)

_ROUND_TRIP = [
    ("harness.planner", _PLANNER_INLINE),
    ("harness.evaluator", _EVALUATOR_INLINE),
    ("orchestrator.reason", _ORCHESTRATOR_INLINE),
]


@pytest.mark.unit
@pytest.mark.parametrize("prompt_id, expected", _ROUND_TRIP)
def test_load_prompt_round_trips_inline_constant(prompt_id: str, expected: str) -> None:
    """Each externalised prompt equals its previously-inline constant, byte-for-byte."""
    assert load_prompt(prompt_id) == expected


@pytest.mark.unit
def test_load_prompt_is_cached() -> None:
    """Repeated loads return the identical cached object (no re-read / re-parse)."""
    first = load_prompt("harness.planner")
    second = load_prompt("harness.planner")
    assert first is second


@pytest.mark.unit
def test_evaluator_prompt_supports_threshold_format() -> None:
    """The evaluator prompt keeps the doubled braces so str.format still works."""
    rendered = load_prompt("harness.evaluator").format(threshold=0.7)
    assert "meet or exceed 0.7" in rendered
    # The escaped {{ }} JSON braces survive into single braces after formatting.
    assert '"quality": <float 0.0-1.0>' in rendered
    assert "{threshold}" not in rendered


@pytest.mark.unit
def test_planner_and_evaluator_preserve_trailing_newline() -> None:
    """Prompts that ended with a trailing newline still do; the base prompt does not."""
    assert load_prompt("harness.planner").endswith("}\n")
    assert load_prompt("harness.evaluator").endswith("}}\n")
    assert not load_prompt("orchestrator.reason").endswith("\n")


@pytest.mark.unit
def test_unknown_prompt_id_raises() -> None:
    """An unregistered id raises a clear PromptNotFoundError listing known ids."""
    with pytest.raises(PromptNotFoundError) as exc:
        load_prompt("does.not.exist")
    assert "does.not.exist" in str(exc.value)


@pytest.mark.unit
def test_every_registered_prompt_loads() -> None:
    """All ids in the registry resolve to a non-empty body (no dead entries)."""
    for prompt_id in _PROMPT_FILES:
        body = load_prompt(prompt_id)
        assert body
        # Front-matter and the fence wrapper must have been stripped.
        assert not body.lstrip().startswith("---")
        assert "```" not in body
