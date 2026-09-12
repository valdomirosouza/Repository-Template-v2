"""Fixture-repo tests for scripts/template_sync.sh (W14-T1, issue #376, ADR-0087).

Builds a template repo and an adopter repo in a temp directory, makes divergent edits, runs the
sync, and asserts the ADR-0087 contract: adopter edits survive, template-only changes fast-forward,
overlapping hunks conflict, excluded paths are never written, .template-version is recorded.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "template_sync.sh"

pytestmark = pytest.mark.unit


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit_all(cwd: Path, msg: str) -> str:
    _git(cwd, "add", "-A")
    _git(cwd, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", msg)
    return _git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path, str]:
    template = tmp_path / "template"
    template.mkdir()
    _git(template, "init", "-q", "-b", "main")
    (template / "Makefile").write_text("all:\n\techo template v1\n")
    (template / "README.md").write_text("# Template\n\nline A\nline B\nline C\n")
    (template / "CLAUDE.md").write_text("template contract v1\n")
    (template / "keep.txt").write_text("unchanged\n")
    (template / "gone.txt").write_text("to be deleted\n")
    base = _commit_all(template, "v1")

    adopter = tmp_path / "adopter"
    shutil.copytree(template, adopter)
    (adopter / ".template-version").write_text(f"{base} 2026-09-12T00:00:00Z\n")
    (adopter / ".template-sync.yml").write_text("exclude:\n  - CLAUDE.md\n")
    # adopter edits: Makefile (template will NOT touch) and README line C (template will touch A)
    (adopter / "Makefile").write_text("all:\n\techo adopter custom\n")
    (adopter / "README.md").write_text("# Template\n\nline A\nline B\nline C adopter\n")
    (adopter / "CLAUDE.md").write_text("adopter contract\n")
    _commit_all(adopter, "adopter customisations")

    # template v2: README line A changes (non-overlapping), keep.txt changes, gone.txt deleted,
    # new.txt added, CLAUDE.md changes (excluded on the adopter side)
    (template / "README.md").write_text("# Template\n\nline A v2\nline B\nline C\n")
    (template / "keep.txt").write_text("changed by template\n")
    (template / "gone.txt").unlink()
    (template / "new.txt").write_text("new in v2\n")
    (template / "CLAUDE.md").write_text("template contract v2\n")
    _commit_all(template, "v2")
    return template, adopter, base


def _run_sync(adopter: Path, template: Path) -> str:
    return subprocess.run(
        ["bash", str(SCRIPT), "--template-url", str(template)],
        cwd=adopter,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_three_way_sync_contract(repos: tuple[Path, Path, str]) -> None:
    template, adopter, base = repos
    out = _run_sync(adopter, template)

    assert (
        adopter / "Makefile"
    ).read_text() == "all:\n\techo adopter custom\n"  # adopter edit survives
    assert (adopter / "keep.txt").read_text() == "changed by template\n"  # fast-forward
    assert (
        adopter / "README.md"
    ).read_text() == "# Template\n\nline A v2\nline B\nline C adopter\n"  # merged
    assert (adopter / "CLAUDE.md").read_text() == "adopter contract\n"  # excluded, untouched
    assert (adopter / "new.txt").exists()  # added
    assert not (adopter / "gone.txt").exists()  # deleted (adopter never modified it)
    assert "CONFLICT      0" in out
    new_tip = _git(template, "rev-parse", "HEAD")
    assert (adopter / ".template-version").read_text().startswith(new_tip)


def test_overlapping_change_leaves_conflict_markers(repos: tuple[Path, Path, str]) -> None:
    template, adopter, _ = repos
    (adopter / "keep.txt").write_text("changed by adopter\n")  # same hunk both sides
    _commit_all(adopter, "adopter keep.txt")
    out = _run_sync(adopter, template)
    text = (adopter / "keep.txt").read_text()
    assert "<<<<<<<" in text and "changed by adopter" in text and "changed by template" in text
    assert "CONFLICT      1" in out


def test_dry_run_writes_nothing(repos: tuple[Path, Path, str]) -> None:
    template, adopter, base = repos
    before = {p: p.read_text() for p in adopter.rglob("*") if p.is_file() and ".git" not in p.parts}
    subprocess.run(
        ["bash", str(SCRIPT), "--template-url", str(template), "--dry-run"],
        cwd=adopter,
        check=True,
        capture_output=True,
        text=True,
    )
    after = {p: p.read_text() for p in adopter.rglob("*") if p.is_file() and ".git" not in p.parts}
    assert before == after
    assert (adopter / ".template-version").read_text().startswith(base)
