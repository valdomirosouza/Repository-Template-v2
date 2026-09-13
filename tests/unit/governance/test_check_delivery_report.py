"""Unit tests for scripts/governance/check_delivery_report.py (W13-T6, issue #371)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_delivery_report as cdr  # noqa: E402

pytestmark = pytest.mark.unit

GOOD = """# FINAL-REPORT — SPEC-AI-001

## 1. Summary
| Phase | Name | Gate |
| --- | --- | --- |
| 6 | Dev | PASS |

## 2. Requirement-traceability table
| Criterion | Phase | ADR(s) | Evidence |
| --- | --- | --- | --- |
| AC-01 | 8 | ADR-0001 | `src/mod.py` |
| AC-02 | 8 | ADR-0001 | `logs/08-test.log` |

## 6. Ambiguity ledger
| Phase | Kind | Item | Owner | Resolve by | Status |
| --- | --- | --- | --- | --- | --- |
| 2 | Assumption | thing | TL | 4 | confirmed |
"""


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "governance").mkdir(parents=True)
    (tmp_path / "docs" / "adr").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "docs" / "governance" / "spec-registry.json").write_text(
        json.dumps({"specs": [{"id": "SPEC-AI-001"}]})
    )
    (tmp_path / "docs" / "adr" / "ADR-0001-x.md").write_text("# x")
    (tmp_path / "src" / "mod.py").write_text("")
    rep_dir = tmp_path / "docs" / "delivery" / "SPEC-AI-001"
    (rep_dir / "logs").mkdir(parents=True)
    (rep_dir / "logs" / "08-test.log").write_text("ok")
    return tmp_path


def test_good_report_passes(tmp_path: Path):
    root = _repo(tmp_path)
    p = root / "docs" / "delivery" / "SPEC-AI-001" / "FINAL-REPORT.md"
    p.write_text(GOOD)
    assert cdr.evaluate(p, root).ok


def test_unknown_spec_dead_adr_and_missing_evidence(tmp_path: Path):
    root = _repo(tmp_path)
    p = root / "docs" / "delivery" / "SPEC-AI-001" / "FINAL-REPORT.md"
    p.write_text(
        GOOD.replace("SPEC-AI-001", "SPEC-AI-999")
        .replace("ADR-0001", "ADR-0999")
        .replace("`src/mod.py`", "`src/nope.py`")
    )
    codes = {e[:2] for e in cdr.evaluate(p, root).errors}
    assert codes == {"D1", "D2", "D3"}


def test_blocking_question_and_overdue_assumption(tmp_path: Path):
    root = _repo(tmp_path)
    p = root / "docs" / "delivery" / "SPEC-AI-001" / "FINAL-REPORT.md"
    p.write_text(
        GOOD
        + "| 3 | Open question | which db? | TL | 4 | blocking |\n| 2 | Assumption | late | TL | 4 | open |\n"
    )
    errs = cdr.evaluate(p, root).errors
    assert any("blocking open question" in e for e in errs)
    assert any("assumption still open past phase 4" in e for e in errs)


def test_real_feat_001_report_validates():
    rep = cdr.evaluate(REPO_ROOT / "docs" / "delivery" / "SPEC-FEAT-001" / "FINAL-REPORT.md")
    assert rep.ok, rep.errors
