"""Unit tests for scripts/check_version_consistency.py (ADR-0057).

version.txt is the single source of truth; pyproject.toml and README must agree.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_version_consistency.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_version_consistency", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _make_repo(tmp_path: Path, *, version_txt: str, pyproject: str, readme: str) -> Path:
    (tmp_path / "version.txt").write_text(version_txt)
    (tmp_path / "pyproject.toml").write_text(pyproject)
    (tmp_path / "README.md").write_text(readme)
    return tmp_path


def test_consistent_versions_pass(mod, tmp_path):
    root = _make_repo(
        tmp_path,
        version_txt="2.6.0\n",
        pyproject='[project]\nname = "x"\nversion = "2.6.0"\n',
        readme="# X\n\n> **Version:** 2.6.0 | Status: Active\n",
    )
    assert mod.check(root) == []


def test_pyproject_mismatch_fails(mod, tmp_path):
    root = _make_repo(
        tmp_path,
        version_txt="2.6.0\n",
        pyproject='[project]\nversion = "2.5.0"\n',
        readme="> **Version:** 2.6.0\n",
    )
    errors = mod.check(root)
    assert any("pyproject.toml version" in e for e in errors)


def test_readme_mismatch_fails(mod, tmp_path):
    root = _make_repo(
        tmp_path,
        version_txt="2.6.0\n",
        pyproject='[project]\nversion = "2.6.0"\n',
        readme="> **Version:** 2.4.0\n",
    )
    errors = mod.check(root)
    assert any("README.md" in e for e in errors)


def test_missing_pyproject_version_fails(mod, tmp_path):
    root = _make_repo(
        tmp_path,
        version_txt="2.6.0\n",
        pyproject='[project]\nname = "x"\n',
        readme="> **Version:** 2.6.0\n",
    )
    errors = mod.check(root)
    assert any("no top-level version" in e for e in errors)


def test_readme_without_version_line_is_ok(mod, tmp_path):
    # README that simply omits a Version line is not an error.
    root = _make_repo(
        tmp_path,
        version_txt="2.6.0\n",
        pyproject='[project]\nversion = "2.6.0"\n',
        readme="# Project\n\nNo version header here.\n",
    )
    assert mod.check(root) == []


def test_real_repository_is_consistent(mod):
    # The committed repo must always pass.
    assert mod.check(_ROOT) == []
