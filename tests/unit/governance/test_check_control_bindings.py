"""Unit tests for the control-binding governance gate (ADR-0061, RFC-0004).

Covers the five required fixtures: a clean PR, an undeclared PII trigger (fail), a SOX
trigger out of scope (exempt/pass), an over-budget declaration (fail), and a 3-domain
atomicity smell (fail) — plus the pure helpers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_control_bindings as cb  # noqa: E402

pytestmark = pytest.mark.unit

TRIGGERS = cb.load_triggers(REPO_ROOT / ".github/control-triggers.yml")
MATRIX = cb.load_matrix(REPO_ROOT / "docs/governance/applicability-matrix.yml")


def _evaluate(changed, diff, declared, *, atomic_exception=False):
    skills, ambient = cb.parse_declarations(declared)
    return cb.evaluate(
        changed_files=changed,
        diff_text=diff,
        declared_skills=skills,
        declared_ambient=ambient,
        triggers=TRIGGERS,
        matrix=MATRIX,
        atomic_exception=atomic_exception,
    )


# --------------------------------------------------------------------- fixtures (the 5)


def test_clean_pr_with_declared_pii_passes():
    rep = _evaluate(
        changed=["src/guardrails/pii_filter.py"],
        diff="+    email = mask(email)  # personal_data\n",
        declared="## Skills — load before executing\n- privacy/pii\n- privacy/lgpd\n",
    )
    assert rep.ok, cb.render(rep)
    assert "personal-data" in rep.fired


def test_pii_trigger_without_declaration_fails():
    rep = _evaluate(
        changed=["src/guardrails/pii_filter.py"],
        diff="+    cpf = user.cpf\n",
        declared="## Skills — load before executing\n- sdlc/spec-lifecycle\n",
    )
    assert not rep.ok
    codes = {v.code for v in rep.violations}
    assert "missing-control" in codes
    assert any("privacy/pii" in v.message for v in rep.violations)


def test_sox_out_of_scope_is_exempt_not_failure():
    rep = _evaluate(
        changed=["src/guardrails/audit_logger.py"],
        diff="+    record_audit(event)  # immutable\n",
        declared="## Skills — load before executing\n",  # nothing declared
    )
    assert rep.ok, cb.render(rep)
    assert any("out of scope" in e for e in rep.exempt)
    assert "audit-log" not in rep.fired  # exempt triggers do not count as fired


def test_over_budget_three_skills_fails():
    rep = _evaluate(
        changed=["README.md"],
        diff="+ docs only\n",
        declared=(
            "## Skills — load before executing\n"
            "- privacy/pii\n- devsecops/owasp-top10\n- change-management/cab-process\n"
        ),
    )
    assert not rep.ok
    assert any(v.code == "budget" for v in rep.violations)


def test_three_domain_atomicity_smell_fails():
    rep = _evaluate(
        changed=[
            "src/guardrails/pii_filter.py",
            "src/api/rest/widgets.py",
            "src/agents/planner.py",
        ],
        diff=("+ email = x  # pii\n+ @router.get('/widgets')\n+ prompt = build_prompt()\n"),
        declared="## Skills — load before executing\n- privacy/pii\n",
    )
    assert not rep.ok
    assert any(v.code == "atomicity" for v in rep.violations)
    assert len(set(rep.fired)) >= 3


# --------------------------------------------------------------------- extra behaviour


def test_atomic_exception_downgrades_atomicity_to_warn():
    rep = _evaluate(
        changed=[
            "src/guardrails/pii_filter.py",
            "src/api/rest/widgets.py",
            "src/agents/planner.py",
        ],
        diff="+ email pii\n+ @router.post('/x')\n+ messages = []\n",
        declared=("## Skills — load before executing\n- privacy/pii\n- privacy/gdpr\n"),
        atomic_exception=True,
    )
    assert not any(v.code == "atomicity" for v in rep.violations)
    assert any("atomicity" in s for s in rep.suppressed)


def test_allow_marker_suppresses_a_trigger():
    rep = _evaluate(
        changed=["src/guardrails/pii_filter.py"],
        diff="+ email = x  # control-binding: ignore personal-data reason=test-fixture only\n",
        declared="## Skills — load before executing\n",
    )
    assert rep.ok, cb.render(rep)
    assert any("personal-data" in s for s in rep.suppressed)


def test_requires_any_satisfied_by_one_jurisdiction():
    rep = _evaluate(
        changed=["src/guardrails/pii_filter.py"],
        diff="+ personal_data = 1\n",
        declared="## Skills — load before executing\n- privacy/pii\n- privacy/gdpr\n",
    )
    assert rep.ok, cb.render(rep)


def test_ambient_adr_required_when_in_scope():
    # cicd-security fires on ci*.yml and requires ADR-0029 (not conditional).
    rep = _evaluate(
        changed=[".github/workflows/ci.yml"],
        diff="+ new step\n",
        declared="## Skills — load before executing\n- devsecops/secret-scanning\n- sbom-sca-gate\n",
    )
    # ci.yml also fires dependency-or-pipeline (needs secret-scanning + sbom-sca-gate, satisfied).
    assert any(v.code == "missing-control" and "ADR-0029" in v.message for v in rep.violations)


def test_content_filter_prevents_false_positive():
    # Touches src/api/rest but adds no endpoint decorator → endpoint trigger must NOT fire.
    rep = _evaluate(
        changed=["src/api/rest/helpers.py"],
        diff="+ def helper():\n+     return 1\n",
        declared="## Skills — load before executing\n",
    )
    assert "endpoint-untrusted-input" not in rep.fired


# --------------------------------------------------------------------- pure helpers


def test_parse_declarations_separates_skills_and_ambient():
    skills, ambient = cb.parse_declarations(
        "## Skills — load before executing\n- privacy/pii\n- ADR-0026\n- sbom-sca-gate\n"
    )
    assert "privacy/pii" in skills
    assert "ADR-0026" in ambient
    assert "sbom-sca-gate" in ambient
    assert "ADR-0026" not in skills


def test_parse_declarations_falls_back_without_header():
    skills, _ = cb.parse_declarations("random text mentioning privacy/pii inline")
    assert "privacy/pii" in skills


def test_added_lines_strips_markers():
    assert cb.added_lines("+++ b/f\n+kept\n-removed\n unchanged") == ["kept"]


def test_path_matches_supports_globs():
    assert cb._path_matches(["src/agents/**"], ["src/agents/x/y.py"])
    assert not cb._path_matches(["src/agents/**"], ["src/api/rest/z.py"])


def test_render_contains_result_line():
    rep = _evaluate(changed=["README.md"], diff="+x\n", declared="")
    assert "RESULT: PASS" in cb.render(rep)


def test_cli_main_passes_on_clean_inputs(tmp_path):
    files = tmp_path / "files.txt"
    files.write_text("README.md\n")
    diff = tmp_path / "diff.txt"
    diff.write_text("+ docs\n")
    declared = tmp_path / "decl.txt"
    declared.write_text("## Skills — load before executing\n- sdlc/spec-lifecycle\n")
    rc = cb.main(
        [
            "--changed-files",
            str(files),
            "--diff",
            str(diff),
            "--declared",
            str(declared),
        ]
    )
    assert rc == 0


def test_cli_main_fails_on_undeclared_trigger(tmp_path):
    files = tmp_path / "files.txt"
    files.write_text("src/guardrails/pii_filter.py\n")
    diff = tmp_path / "diff.txt"
    diff.write_text("+ email = pii\n")
    declared = tmp_path / "decl.txt"
    declared.write_text("## Skills — load before executing\n")
    rc = cb.main(
        [
            "--changed-files",
            str(files),
            "--diff",
            str(diff),
            "--declared",
            str(declared),
        ]
    )
    assert rc == 1
