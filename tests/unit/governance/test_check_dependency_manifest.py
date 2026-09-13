"""Unit tests for the dependency-manifest gate (W12-T9, issue #362)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_dependency_manifest as dm  # noqa: E402

pytestmark = pytest.mark.unit

PYPROJECT = """
dependencies = [
    "anthropic>=0.28.0",
    "redis[asyncio]>=5.0.0",
]
"""
UVLOCK = '[[package]]\nname = "anthropic"\nversion = "0.104.1"\n\n[[package]]\nname = "redis"\nversion = "7.4.0"\n'
CONFIG = '    llm_model: str = "claude-sonnet-5"\n'


def _manifest(**over):
    m = {
        "last_updated": "2026-09-01",
        "python_packages": [{"name": "anthropic", "version_constraint": ">=0.28.0"}],
        "ai_dependencies": [
            {
                "models": [
                    {
                        "model_id": "claude-sonnet-5",
                        "used_by": ["src/shared/config.py"],
                        "last_contract_tested": "2026-09-01",
                        "contract_test_suite": "tests/model_contract/",
                    }
                ]
            }
        ],
    }
    m.update(over)
    return m


def _run(manifest, *, today=date(2026, 9, 12), config=CONFIG, pyproject=PYPROJECT):
    return dm.evaluate(
        manifest=manifest,
        pyproject_text=pyproject,
        uvlock_text=UVLOCK,
        config_text=config,
        env_text="",
        today=today,
        max_age_days=92,
        repo_root=REPO_ROOT,
    )


def test_consistent_manifest_passes():
    assert _run(_manifest()).ok


def test_m1_constraint_mismatch_and_undeclared_package():
    rep = _run(
        _manifest(
            python_packages=[
                {"name": "anthropic", "version_constraint": ">=0.90.0"},
                {"name": "ghost", "version_constraint": ">=1"},
            ]
        )
    )
    assert any(e.startswith("M1") and "anthropic" in e for e in rep.errors)
    assert any(e.startswith("M1") and "ghost" in e for e in rep.errors)
    assert any(e.startswith("M5") and "ghost" in e for e in rep.errors)


def test_m2_used_model_must_be_selectable_and_default_must_be_listed():
    rep = _run(_manifest(), config='    llm_model: str = "claude-sonnet-4-6"\n')
    assert any(
        e.startswith("M2") and "claude-sonnet-5" in e for e in rep.errors
    )  # used_by but absent
    assert any(
        e.startswith("M2") and "claude-sonnet-4-6" in e for e in rep.errors
    )  # default not listed


def test_m3_staleness_of_manifest_and_contract_test():
    rep = _run(_manifest(last_updated="2026-05-28"), today=date(2026, 9, 12))
    assert any(e.startswith("M3") and "last_updated" in e for e in rep.errors)
    m = _manifest()
    m["ai_dependencies"][0]["models"][0]["last_contract_tested"] = "2026-06-06"
    rep = _run(m)
    assert any(e.startswith("M3") and "last_contract_tested" in e for e in rep.errors)


def test_m4_paths_must_exist():
    m = _manifest()
    m["ai_dependencies"][0]["models"][0]["used_by"] = ["src/does/not/exist.py"]
    rep = _run(m, config='    llm_model: str = "claude-sonnet-5"\n# src/does/not/exist.py\n')
    assert any(e.startswith("M4") for e in rep.errors)


def test_pyproject_constraint_parser_handles_extras():
    assert dm.pyproject_constraints(PYPROJECT) == {"anthropic": ">=0.28.0", "redis": ">=5.0.0"}


def test_real_manifest_is_consistent():
    """The committed manifest agrees with pyproject/uv.lock/config (M1/M2/M4/M5).

    Freshness (M3) is deliberately NOT asserted here: the report-mode CI gate owns it, and on
    2026-09-12 the manifest *is* stale until the W14-T3 model promotion re-runs the contract
    suite. A unit test must not paper over that with a fake date.
    """
    rep = dm.evaluate(
        manifest=yaml.safe_load(dm.MANIFEST.read_text()),
        pyproject_text=dm.PYPROJECT.read_text(),
        uvlock_text=dm.UVLOCK.read_text(),
        config_text=dm.CONFIG.read_text(),
        env_text=dm.ENV_EXAMPLE.read_text(),
        today=date.today(),
        max_age_days=10**6,
    )
    assert rep.ok, dm.render(rep)
