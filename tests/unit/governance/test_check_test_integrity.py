"""Unit tests for the test-integrity governance gate (ADR-0065).

Covers the two enforced invariants — no silent test-count decrease (with the TEST-WAIVER
escape hatch) and no unjustified skip/xfail — plus the static `ast` counter and the CLI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_test_integrity as ti  # noqa: E402

pytestmark = pytest.mark.unit


def _counts(total: int, **per: int) -> ti.TestCounts:
    return ti.TestCounts(total=total, per_marker=dict(per))


# --------------------------------------------------------------------- count-drop invariant


def test_stable_count_passes():
    rep = ti.evaluate(
        before=_counts(10, unit=10),
        after=_counts(10, unit=10),
        diff_text="",
        waiver_text="",
    )
    assert rep.ok, ti.render(rep)


def test_count_increase_passes():
    rep = ti.evaluate(
        before=_counts(10, unit=10),
        after=_counts(12, unit=12),
        diff_text="+def test_new():\n",
        waiver_text="",
    )
    assert rep.ok, ti.render(rep)


def test_silent_deletion_fails():
    # Simulated test deletion: total drops with no waiver.
    rep = ti.evaluate(
        before=_counts(10, unit=10),
        after=_counts(7, unit=7),
        diff_text="-def test_old():\n",
        waiver_text="",
    )
    assert not rep.ok
    assert any(v.code == "test-count-drop" for v in rep.violations)


def test_per_marker_drop_fails_even_if_total_holds():
    # Total unchanged but a marker bucket shrank (strong tests swapped for weak ones elsewhere).
    rep = ti.evaluate(
        before=_counts(10, unit=8, security=2),
        after=_counts(10, unit=10, security=0),
        diff_text="",
        waiver_text="",
    )
    assert not rep.ok
    assert any("security" in v.message for v in rep.violations)


def test_deletion_with_waiver_passes():
    rep = ti.evaluate(
        before=_counts(10, unit=10),
        after=_counts(7, unit=7),
        diff_text="-def test_old():\n",
        waiver_text="TEST-WAIVER: removed three obsolete tests for the deprecated v1 endpoint",
    )
    assert rep.ok, ti.render(rep)
    assert rep.waivers


def test_waiver_in_diff_also_counts():
    rep = ti.evaluate(
        before=_counts(5, unit=5),
        after=_counts(4, unit=4),
        diff_text="+# TEST-WAIVER: merged two duplicate cases into one parametrize\n",
        waiver_text="",
    )
    assert rep.ok, ti.render(rep)


# --------------------------------------------------------------------- skip/xfail invariant


def test_unjustified_skip_fails():
    rep = ti.evaluate(
        before=_counts(5),
        after=_counts(5),
        diff_text="+    @pytest.mark.skip\n+    def test_flaky():\n",
        waiver_text="",
    )
    assert not rep.ok
    assert any(v.code == "unjustified-skip" for v in rep.violations)


def test_skip_with_reason_kwarg_passes():
    rep = ti.evaluate(
        before=_counts(5),
        after=_counts(5),
        diff_text='+    @pytest.mark.skip(reason="waiting on upstream fix #123")\n',
        waiver_text="",
    )
    assert rep.ok, ti.render(rep)


def test_skip_with_inline_comment_passes():
    rep = ti.evaluate(
        before=_counts(5),
        after=_counts(5),
        diff_text="+    @pytest.mark.xfail  # known bug, tracked in JIRA-42\n",
        waiver_text="",
    )
    assert rep.ok, ti.render(rep)


def test_pytest_skip_call_with_string_passes():
    rep = ti.evaluate(
        before=_counts(5),
        after=_counts(5),
        diff_text='+        pytest.skip("integration infra not available")\n',
        waiver_text="",
    )
    assert rep.ok, ti.render(rep)


# --------------------------------------------------------------------- static ast counter


def test_count_tests_in_source_attributes_markers():
    src = (
        "import pytest\n"
        "pytestmark = pytest.mark.unit\n"
        "def test_a():\n    assert True\n"
        "@pytest.mark.security\n"
        "def test_b():\n    assert True\n"
        "class TestGroup:\n"
        "    def test_c(self):\n        assert True\n"
        "def helper():\n    return 1\n"
    )
    total, by_marker = ti.count_tests_in_source(src)
    assert total == 3  # test_a, test_b, TestGroup::test_c — helper() excluded
    assert by_marker["unit"]  # module-level marker applied to test_a (and others)
    assert "security" in by_marker  # decorator marker on test_b


def test_count_tests_handles_syntax_error_gracefully():
    total, by_marker = ti.count_tests_in_source("def test_oops(:\n")
    assert total == 0
    assert by_marker == {}


def test_count_tests_walks_a_tree(tmp_path):
    (tmp_path / "test_one.py").write_text(
        "def test_x():\n    assert 1\ndef test_y():\n    assert 1\n"
    )
    (tmp_path / "helpers.py").write_text("def test_should_be_ignored():\n    assert 1\n")
    counts = ti.count_tests(tmp_path)
    assert counts.total == 2  # only test_*.py / *_test.py files are scanned (helpers.py excluded)


# --------------------------------------------------------------------- helpers + CLI


def test_added_lines_and_waiver_parsing():
    assert ti.added_lines("+++ b/f\n+kept\n-gone\n ctx") == ["kept"]
    assert ti.parse_waivers("noise\nTEST-WAIVER: because reasons\n") == ["because reasons"]


def test_baseline_roundtrip(tmp_path):
    counts = _counts(3, unit=2, security=1)
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps(counts.to_json()))
    restored = ti.TestCounts.from_json(json.loads(p.read_text()))
    assert restored == counts


def test_cli_update_baseline_then_pass(tmp_path):
    root = tmp_path / "tests"
    root.mkdir()
    (root / "test_sample.py").write_text(
        "def test_a():\n    assert 1\ndef test_b():\n    assert 1\n"
    )
    baseline = tmp_path / "baseline.json"
    assert ti.main(["--root", str(root), "--baseline", str(baseline), "--update-baseline"]) == 0
    assert baseline.exists()
    # With the baseline matching the tree and an empty diff, the gate passes.
    assert ti.main(["--root", str(root), "--baseline", str(baseline)]) == 0


def test_cli_fails_on_deletion(tmp_path):
    root = tmp_path / "tests"
    root.mkdir()
    (root / "test_sample.py").write_text(
        "def test_a():\n    assert 1\ndef test_b():\n    assert 1\n"
    )
    baseline = tmp_path / "baseline.json"
    ti.main(["--root", str(root), "--baseline", str(baseline), "--update-baseline"])
    # Delete a test → tree now has fewer than the baseline; no waiver ⇒ fail.
    (root / "test_sample.py").write_text("def test_a():\n    assert 1\n")
    assert ti.main(["--root", str(root), "--baseline", str(baseline)]) == 1
