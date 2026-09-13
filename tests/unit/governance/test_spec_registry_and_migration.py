"""Unit tests for build_spec_registry.py (W13-T3) and migrate_spec_frontmatter.py (W13-T2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import build_spec_registry as reg  # noqa: E402
import migrate_spec_frontmatter as mig  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.requirement("SPEC-SDLC-001")]


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "specs" / "ai").mkdir(parents=True)
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "governance").mkdir(parents=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs" / "adr" / "ADR-0001-x.md").write_text("# x\n")
    (tmp_path / "services.yaml").write_text(
        "services:\n  - name: svc\n    spec: specs/ai/good.md\n"
    )
    (tmp_path / "specs" / "ai" / "good.md").write_text(
        "---\nid: SPEC-AI-001\nkind: spec\nstatus: approved\ngoverning_adrs: [ADR-0001]\n"
        "implemented_by: [src/mod.py]\nverified_by: []\n---\n# good\n"
    )
    (tmp_path / "src" / "mod.py").write_text('"""m\n\nSpec: specs/ai/good.md\n"""\n')
    (tmp_path / "tests" / "test_mod.py").write_text(
        'import pytest\npytestmark = [pytest.mark.unit, pytest.mark.requirement("SPEC-AI-001/FR-01")]\n'
    )
    return tmp_path


def test_consistent_repo_passes_and_registry_links_hops(tmp_path: Path):
    rep = reg.evaluate(_repo(tmp_path))
    assert rep.ok, rep.errors
    spec = rep.specs[0]
    assert spec["implemented_by"] == ["src/mod.py"]
    assert spec["verified_by"] == []  # explicit list wins over harvested refs
    assert spec["requirement_tests"] == ["tests/test_mod.py (FR-01)"]


def test_s1_s2_s3_s4_s5_rules(tmp_path: Path):
    root = _repo(tmp_path)
    (root / "specs" / "ai" / "nofm.md").write_text("# no frontmatter\n")
    (root / "specs" / "ai" / "bad.md").write_text(
        "---\nid: SPEC-1\nkind: spec\nstatus: Approved\ngoverning_adrs: [ADR-9999]\n"
        "implemented_by: [src/missing.py]\n---\n"
    )
    (root / "specs" / "ai" / "unclaimed.md").write_text(
        "---\nid: SPEC-AI-002\nkind: spec\nstatus: approved\n---\n"
    )
    (root / "specs" / "ai" / "policy.md").write_text(
        "---\nid: SPEC-AI-003\nkind: policy\nstatus: approved\n---\n"
    )
    codes = {e[:2] for e in reg.evaluate(root).errors}
    assert codes >= {"S1", "S2", "S3", "S4", "S5"}
    assert not any("SPEC-AI-003" in e for e in reg.evaluate(root).errors)  # policy exempt from S5


def test_s6_and_s7(tmp_path: Path):
    root = _repo(tmp_path)
    (root / "src" / "orphan.py").write_text('"""o\n\nSpec: specs/ai/ghost.md\n"""\n')
    (root / "services.yaml").write_text(
        "services:\n  - name: svc\n    spec: specs/ai/ghost.md\n  - name: nospec\n"
    )
    rep = reg.evaluate(root)
    assert any(e.startswith("S6") for e in rep.errors)
    assert any(e.startswith("S7") and "ghost" in e for e in rep.errors)
    assert any(w.startswith("S7") and "nospec" in w for w in rep.warnings)


def test_domain_codes_with_digits_are_valid():
    assert reg._ID_RE.match("SPEC-K8S-001")
    assert not reg._ID_RE.match("SPEC-k8s-1")


def test_migration_carries_body_status_and_never_promotes():
    fm = mig.build_frontmatter(
        "specs/x/a.md",
        "# A\n\n**Status:** Approved | **Owner:** Tech Lead\n**ADR references:** ADR-0003, ADR-0011\n",
        spec_id="SPEC-X-001",
        kind="spec",
        refs={"specs/x/a.md": (["src/a.py"], ["tests/test_a.py"])},
        today="2026-09-12",
    )
    assert "status: approved" in fm and "status_source: body-header:Approved" in fm
    assert "owner: Tech Lead" in fm and "- ADR-0003" in fm and "- ADR-0011" in fm
    assert "  - src/a.py" in fm and "  - tests/test_a.py" in fm

    fm2 = mig.build_frontmatter(
        "specs/x/b.md",
        "# B\n\nno header\n",
        spec_id="SPEC-X-002",
        kind="spec",
        refs={},
        today="2026-09-12",
    )
    assert "status: draft" in fm2 and "status_source: default" in fm2 and "owner: unassigned" in fm2


def test_allocate_id_skips_used_and_detects_companions():
    used = {"SPEC-AI-001", "SPEC-AI-010"}
    assert mig.allocate_id("ai", "foo", used) == ("SPEC-AI-002", "spec")
    assert mig.allocate_id("security", "threat-model-SPEC-LGS-001-x", set()) == (
        "SPEC-LGS-001",
        "threat-model",
    )
    assert mig.allocate_id("features", "SPEC-LGS-001-golden-signals-feature-spec", set()) == (
        "SPEC-LGS-001",
        "feature-spec",
    )


def test_real_repository_registry_is_clean_and_fresh():
    rep = reg.evaluate()
    assert rep.ok, "\n".join(rep.errors)
    assert reg.OUT_MD.read_text(encoding="utf-8") == reg.render_markdown(rep), (
        "run `make spec-registry`"
    )
