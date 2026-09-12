"""Unit tests for the doc-consistency governance gate (W11-T7, issue #352)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_doc_consistency as dc  # noqa: E402

pytestmark = pytest.mark.unit


def _repo(
    tmp_path: Path, *, readme_n: int = 2, claude_hi: str = "0002", primer_hi: str = "0002"
) -> Path:
    adr = tmp_path / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "ADR-0001-first.md").write_text("# one\n")
    (adr / "ADR-0002-second.md").write_text("# two\n")
    (adr / "README.md").write_text(
        "| [ADR-0001](ADR-0001-first.md) |\n| [ADR-0002](ADR-0002-second.md) |\n"
    )
    (tmp_path / "README.md").write_text(
        f"All {readme_n} ADRs are recorded in [x](docs/adr/README.md).\n"
    )
    (tmp_path / "CLAUDE.md").write_text(
        "| ADRs | ADR-0001\u2013ADR-" + claude_hi + ", all binding |\n"
    )
    (tmp_path / "CLAUDE_SESSION_INIT.md").write_text(
        f"## ADR Quick Index (most recent)\n\n| ADR | D |\n| --- | --- |\n| ADR-0001 | a |\n| ADR-{primer_hi} | b |\n\nFull index\n"
    )
    return tmp_path


def test_consistent_repo_passes(tmp_path: Path):
    rep = dc.evaluate(_repo(tmp_path))
    assert rep.ok, rep.errors


def test_c1_readme_count(tmp_path: Path):
    rep = dc.evaluate(_repo(tmp_path, readme_n=51))
    assert [e for e in rep.errors if e.startswith("C1")]


def test_c2_claude_range(tmp_path: Path):
    rep = dc.evaluate(_repo(tmp_path, claude_hi="0001"))
    assert [e for e in rep.errors if e.startswith("C2")]


def test_c3_primer_quick_index_must_reach_highest(tmp_path: Path):
    rep = dc.evaluate(_repo(tmp_path, primer_hi="0001"))
    assert [e for e in rep.errors if e.startswith("C3")]


def test_c4_index_must_list_every_adr(tmp_path: Path):
    root = _repo(tmp_path)
    (root / "docs" / "adr" / "ADR-0003-third.md").write_text("# three\n")
    rep = dc.evaluate(root, links=False)
    assert any(e.startswith("C4") and "ADR-0003" in e for e in rep.errors)


def test_l1_dangling_relative_link_and_placeholders(tmp_path: Path):
    root = _repo(tmp_path)
    (root / "docs" / "guide.md").write_text(
        "[ok](adr/ADR-0001-first.md) [gone](adr/nope.md) [tpl](FEAT-{id}/x.md) [web](https://x.y) [anchor](#top)\n"
    )
    rep = dc.evaluate(root)
    l1 = [e for e in rep.errors if e.startswith("L1")]
    assert len(l1) == 1 and "nope.md" in l1[0]
    assert (
        rep.links_checked == 5
    )  # README(1) + adr index(2) + ok + gone; placeholder/http/anchor skipped


def test_real_repository_is_consistent():
    rep = dc.evaluate()
    assert rep.ok, dc.render(rep)
