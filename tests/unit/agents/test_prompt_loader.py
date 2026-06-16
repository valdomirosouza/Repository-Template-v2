"""Tests for the versioned on-disk prompt loader (ADR-0079).

Externalising the evaluator + orchestrator-reason prompts must not change runtime
behaviour: the loaded body has to be byte-identical to the former inline constant.
These tests pin that invariant with frozen literal copies so a silent edit to a
prompt file (e.g. a stray reformat) fails CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agents.prompts import (
    PromptDefinition,
    PromptError,
    load_prompt,
    load_prompt_definition,
)
from src.agents.prompts.loader import _PROMPT_PATHS

# ── Frozen copies of the former inline prompts (byte-identical expectation) ──────

# Live src/agents/harness/evaluator.py::_SYSTEM_PROMPT — now evaluate.v2.md (ADR-0080):
# v1 body PLUS the separate `groundedness` SLI field. Pinned byte-identically so a
# stray reformat of the prompt file fails CI. The four scored dimensions and the
# `{threshold}` pass rule are unchanged from v1.
_EXPECTED_EVALUATOR = """\
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

Also report a separate groundedness signal (0.0 to 1.0). This is NOT one of the
four scored dimensions and does NOT affect pass/fail — it is a safety metric:
  - groundedness: The fraction of the implementation's claims that trace back to
    the provided sprint objectives and success criteria. 1.0 = every claim is
    fully grounded in the provided spec/success-criteria; lower = the
    implementation asserts invented, unsupported, or out-of-scope behaviour that
    is not traceable to what was asked.

Respond with valid JSON:
{{
  "quality": <float 0.0-1.0>,
  "originality": <float 0.0-1.0>,
  "craft": <float 0.0-1.0>,
  "functionality": <float 0.0-1.0>,
  "groundedness": <float 0.0-1.0>,
  "feedback": "<specific, actionable feedback — what failed and why>",
  "criteria_results": {{
    "<criterion text>": true|false
  }}
}}
"""

# Former src/agents/orchestrator/orchestrator.py reason BASE string (no trailing newline).
_EXPECTED_REASON_BASE = (
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

_REGISTERED_IDS = sorted(_PROMPT_PATHS)


# ── Loading & byte-identity ─────────────────────────────────────────────────────


def test_evaluator_prompt_byte_identical():
    assert load_prompt("harness.evaluator") == _EXPECTED_EVALUATOR


def test_evaluator_prompt_format_threshold_round_trips():
    """`.format(threshold=...)` must still work and leave no stray braces."""
    rendered = load_prompt("harness.evaluator").format(threshold=0.7)
    assert "meet or exceed 0.7" in rendered
    assert "{threshold}" not in rendered
    # Escaped braces collapse to single braces in the JSON example.
    assert '"quality": <float 0.0-1.0>' in rendered


def test_reason_base_prompt_byte_identical_with_strip():
    assert load_prompt("orchestrator.reason", strip_trailing_newline=True) == _EXPECTED_REASON_BASE


def test_reason_prompt_unstripped_has_trailing_newline():
    raw = load_prompt("orchestrator.reason")
    assert raw.endswith("\n")
    assert raw[:-1] == _EXPECTED_REASON_BASE


def test_call_sites_use_loaded_prompt():
    """The live module constants must come from the loader (no inline drift)."""
    from src.agents.harness.evaluator import _SYSTEM_PROMPT
    from src.agents.orchestrator.orchestrator import _REASON_BASE_SYSTEM_PROMPT

    assert _SYSTEM_PROMPT == _EXPECTED_EVALUATOR
    assert _REASON_BASE_SYSTEM_PROMPT == _EXPECTED_REASON_BASE


# ── Front-matter parsing & validation ───────────────────────────────────────────


@pytest.mark.parametrize("prompt_id", _REGISTERED_IDS)
def test_definition_front_matter_valid(prompt_id: str):
    defn = load_prompt_definition(prompt_id)
    assert isinstance(defn, PromptDefinition)
    assert defn.id == prompt_id
    assert defn.version  # version pin present (e.g. "1.0", or "2.0" for evaluator v2)
    assert defn.owner == "AI Governance Lead"
    assert defn.model  # model pin present
    assert defn.eval_dataset == "tests/model_contract/"
    if prompt_id == "harness.evaluator":
        # evaluate.v2.md supersedes v1 (ADR-0080 — groundedness SLI added).
        assert defn.version == "2.0"
        assert defn.supersedes == "evaluator/evaluate.v1.md"
    else:
        assert defn.version == "1.0"
        assert defn.supersedes is None


@pytest.mark.parametrize("prompt_id", _REGISTERED_IDS)
def test_body_non_empty_and_parses(prompt_id: str):
    body = load_prompt(prompt_id)
    assert body.strip(), f"{prompt_id} body is empty"
    assert "You are" in body


def test_unknown_id_raises():
    with pytest.raises(PromptError, match="unknown prompt id"):
        load_prompt("does.not.exist")


def test_missing_front_matter_raises(tmp_path, monkeypatch):
    bad = tmp_path / "bad.md"
    bad.write_text("```text\nbody only, no front-matter\n```\n", encoding="utf-8")
    monkeypatch.setitem(_PROMPT_PATHS, "test.bad", "bad.md")
    monkeypatch.setattr("src.agents.prompts.loader._PROMPTS_DIR", tmp_path)
    with pytest.raises(PromptError, match="front-matter"):
        load_prompt("test.bad")


def test_id_mismatch_raises(tmp_path, monkeypatch):
    bad = tmp_path / "mismatch.md"
    bad.write_text(
        "---\nid: wrong.id\nversion: 1.0\nowner: x\nmodel: m\n"
        "eval_dataset: d\nsupersedes: null\n---\n```text\nYou are an agent.\n```\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(_PROMPT_PATHS, "test.mismatch", "mismatch.md")
    monkeypatch.setattr("src.agents.prompts.loader._PROMPTS_DIR", tmp_path)
    with pytest.raises(PromptError, match="does not match"):
        load_prompt("test.mismatch")


def test_missing_body_fence_raises(tmp_path, monkeypatch):
    bad = tmp_path / "nobody.md"
    bad.write_text(
        "---\nid: test.nobody\nversion: 1.0\nowner: x\nmodel: m\n"
        "eval_dataset: d\nsupersedes: null\n---\nno fenced block here\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(_PROMPT_PATHS, "test.nobody", "nobody.md")
    monkeypatch.setattr("src.agents.prompts.loader._PROMPTS_DIR", tmp_path)
    with pytest.raises(PromptError, match="fenced prompt body"):
        load_prompt("test.nobody")


def test_prompt_files_exist_on_disk():
    root = Path(__file__).resolve().parents[3] / "prompts"
    for rel in _PROMPT_PATHS.values():
        assert (root / rel).is_file(), f"missing prompt file: {rel}"
