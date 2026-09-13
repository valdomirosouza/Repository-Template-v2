"""Unit tests for the open-questions governance gate (W11-T5, issue #350)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_open_questions as oq  # noqa: E402

pytestmark = pytest.mark.unit


def _spec(status: str, section: str) -> str:
    return f"---\nid: SPEC-TST-001\nstatus: {status}\n---\n\n## 1. Context\n\ntext\n\n## 15. Open Questions\n\n{section}\n\n## 16. References\n\n- none\n"


def test_draft_specs_are_not_checked():
    rep = oq.evaluate({"specs/a.md": _spec("draft", "1. Totally unresolved?")})
    assert rep.ok and rep.checked == 0


def test_approved_spec_with_unresolved_item_fails():
    rep = oq.evaluate({"specs/a.md": _spec("approved", "1. Keep JSON or problem+json?")})
    assert not rep.ok
    assert rep.findings[0].spec == "specs/a.md"
    assert "problem+json" in rep.findings[0].item


def test_resolution_marker_needs_a_reference():
    rep = oq.evaluate(
        {"specs/a.md": _spec("implemented", "1. Keep JSON? _(resolved)_ we kept it.")}
    )
    assert not rep.ok  # 'resolved' without ADR/#issue reference is not traceable


@pytest.mark.parametrize(
    "line",
    [
        "1. Keep JSON? **Resolved in ADR-0076** — kept application/json.",
        "- Typed AppError now? _Deferred_, tracked in #351.",
        "2. Sizing _(resolved — example)_: fake figures.",
        "3. MSK auth — DECIDED per §14: IAM via IRSA.",
        "4. Retention window — closed by RFC-0021.",
    ],
)
def test_resolved_items_pass(line: str):
    rep = oq.evaluate({"specs/a.md": _spec("approved", line)})
    assert rep.ok, rep.findings


def test_none_section_passes():
    rep = oq.evaluate({"specs/a.md": _spec("approved", "None.")})
    assert rep.ok


def test_html_comments_and_blockquotes_are_ignored():
    body = "<!-- Anything unresolved goes here -->\n\n> ⚠️ illustrative values\n\n1. Q _(resolved — example)_"
    rep = oq.evaluate({"specs/a.md": _spec("approved", body)})
    assert rep.ok


def test_continuation_lines_belong_to_the_item():
    body = "1. A long question that wraps\n   onto the next line — resolved in\n   ADR-0001."
    rep = oq.evaluate({"specs/a.md": _spec("approved", body)})
    assert rep.ok


def test_missing_section_is_noted_not_failed():
    text = "---\nstatus: approved\n---\n\n## 1. Context\n\nno §15 here\n"
    rep = oq.evaluate({"specs/a.md": text})
    assert rep.ok and rep.unchecked == ["specs/a.md"]


def test_real_specs_are_clean():
    """Every approved/implemented spec on main has its open questions resolved (W11-T5 fix)."""
    rep = oq.evaluate(oq.load_specs())
    assert rep.ok, oq.render(rep)
