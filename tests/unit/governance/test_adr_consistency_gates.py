"""Unit tests for the ADR consistency governance gates (audit follow-up).

Covers scripts/governance/check_adr_index_status.py and check_doc_references.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GOV = _REPO_ROOT / "scripts" / "governance"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _GOV / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


index_mod = _load("check_adr_index_status")
ref_mod = _load("check_doc_references")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- check_adr_index_status ------------------------------------------------------------------

def _make_adr_repo(tmp_path: Path, *, file_status: str, index_status: str) -> Path:
    adr = tmp_path / "docs" / "adr"
    _write(adr / "ADR-0001-thing.md", f"# ADR-0001 — Thing\n\n**Status:** {file_status}\n")
    _write(
        adr / "README.md",
        "| ADR | Title | Status | Date |\n| --- | --- | --- | --- |\n"
        f"| [ADR-0001](ADR-0001-thing.md) | Thing | {index_status} | 2026-01-01 |\n",
    )
    return tmp_path


def test_index_status_agrees(tmp_path: Path) -> None:
    repo = _make_adr_repo(tmp_path, file_status="Accepted", index_status="Accepted")
    assert index_mod.check(repo) == []


def test_index_status_mismatch_detected(tmp_path: Path) -> None:
    repo = _make_adr_repo(tmp_path, file_status="Proposed", index_status="Accepted")
    problems = index_mod.check(repo)
    assert len(problems) == 1
    assert "ADR-0001" in problems[0] and "proposed" in problems[0] and "accepted" in problems[0]


def test_index_status_handles_table_header_and_qualifier(tmp_path: Path) -> None:
    """Table-format header (| **Status** | ... |) and a trailing qualifier both normalise."""
    adr = tmp_path / "docs" / "adr"
    _write(adr / "ADR-0002-t.md", "# ADR-0002\n\n| **Status** | Accepted (extended by ADR-0009) |\n")
    _write(
        adr / "README.md",
        "| ADR | Status |\n| --- | --- |\n| [ADR-0002](ADR-0002-t.md) | Accepted |\n",
    )
    assert index_mod.check(tmp_path) == []


def test_index_missing_row(tmp_path: Path) -> None:
    adr = tmp_path / "docs" / "adr"
    _write(adr / "ADR-0003-x.md", "**Status:** Accepted\n")
    _write(adr / "README.md", "| ADR | Status |\n| --- | --- |\n")
    problems = index_mod.check(tmp_path)
    assert any("missing from the index" in p for p in problems)


# --- check_doc_references --------------------------------------------------------------------

def test_reference_valid_link(tmp_path: Path) -> None:
    adr = tmp_path / "docs" / "adr"
    _write(adr / "ADR-0001-a.md", "See [ADR-0002](ADR-0002-b.md).\n")
    _write(adr / "ADR-0002-b.md", "# ADR-0002\n")
    errors, _warnings, scanned = ref_mod.check(tmp_path)
    assert errors == [] and scanned == 1


def test_reference_broken_slug_detected(tmp_path: Path) -> None:
    adr = tmp_path / "docs" / "adr"
    _write(adr / "ADR-0001-a.md", "See [ADR-0002](ADR-0002-wrong-name.md).\n")
    _write(adr / "ADR-0002-b.md", "# ADR-0002\n")
    errors, _warnings, _scanned = ref_mod.check(tmp_path)
    assert len(errors) == 1 and "ADR-0002-wrong-name.md" in errors[0]


def test_reference_deprecated_is_warning_not_error(tmp_path: Path) -> None:
    adr = tmp_path / "docs" / "adr"
    _write(adr / "ADR-0001-a.md", "Driven by [the directive](old-directive-ADR-0099-x.md).\n")
    _write(tmp_path / "deprecated" / "old-directive-ADR-0099-x.md", "archived\n")
    errors, warnings, _scanned = ref_mod.check(tmp_path)
    assert errors == [] and len(warnings) == 1


def test_reference_ignores_http_links(tmp_path: Path) -> None:
    adr = tmp_path / "docs" / "adr"
    _write(adr / "ADR-0001-a.md", "[x](https://example.com/ADR-0002-b.md)\n")
    errors, _warnings, scanned = ref_mod.check(tmp_path)
    assert errors == [] and scanned == 0


@pytest.mark.parametrize("mod", [index_mod, ref_mod])
def test_real_repo_report_mode_never_raises(mod) -> None:
    """check() runs cleanly against the real repo (content correctness is asserted elsewhere)."""
    result = mod.check(_REPO_ROOT)
    assert isinstance(result, (list, tuple))
