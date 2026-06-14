"""Unit tests for the Wave-1 traceability governance gates.

Covers the three scripts wired into `make verify-traceability`:
  - check_traceability         (service → ADR / topic / schema / depends_on / SLO chain)
  - check_service_slo_files    (per-service canary SLO files for type:api services)
  - check_runbook_links        (every referenced runbook resolves)

Each script is asserted green against the real repo (so the gate cannot silently start failing on
main) and red against a crafted broken fixture (so the gate cannot silently stop catching things).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_runbook_links as crl  # noqa: E402
import check_service_slo_files as cssf  # noqa: E402
import check_traceability as ct  # noqa: E402

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------- happy path (real repo)


def test_traceability_chain_is_consistent_on_real_repo():
    assert ct.check() == []


def test_every_api_service_has_valid_slo_file_on_real_repo():
    assert cssf.check() == []


def test_all_runbook_references_resolve_on_real_repo():
    problems, scanned = crl.check()
    assert problems == []
    assert scanned > 0  # the gate is actually scanning something


# --------------------------------------------------------------------- check_traceability failures


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_traceability_flags_missing_adr_topic_and_slo(tmp_path):
    services = _write(
        tmp_path / "services.yaml",
        """
services:
  - name: ghost-api
    type: api
    adr:
      - ADR-9999  # does not exist on disk
    publishes:
      - undefined.topic.v1
    depends_on:
      - nonexistent-service
topics:
  - name: real.topic.v1
    schema: infrastructure/does/not/exist.avsc
""",
    )
    problems = ct.check(services)
    blob = "\n".join(problems)
    assert "ADR-9999" in blob
    assert "undefined.topic.v1" in blob
    assert "nonexistent-service" in blob
    assert "exist.avsc" in blob
    assert "ghost-api" in blob  # type:api with no SLO file flagged


# --------------------------------------------------------------------- check_service_slo_files failures


def test_slo_check_flags_missing_file(tmp_path):
    services = _write(
        tmp_path / "services.yaml",
        "services:\n  - name: lonely-api\n    type: api\n",
    )
    slo_dir = tmp_path / "slo"
    slo_dir.mkdir()
    problems = cssf.check(services_path=services, slo_dir=slo_dir)
    assert any("lonely-api" in p and "missing" in p for p in problems)


def test_slo_check_flags_bad_canary_values(tmp_path):
    services = _write(
        tmp_path / "services.yaml",
        "services:\n  - name: bad-api\n    type: api\n",
    )
    slo_dir = tmp_path / "slo"
    slo_dir.mkdir()
    _write(
        slo_dir / "bad-api.yaml",
        # error_rate_max out of range, p99 non-positive, budget missing
        "service: bad-api\ncanary:\n  error_rate_max: 5\n  p99_latency_seconds_max: 0\n",
    )
    problems = cssf.check(services_path=services, slo_dir=slo_dir)
    blob = "\n".join(problems)
    assert "error_rate_max" in blob
    assert "p99_latency_seconds_max" in blob
    assert "error_budget_min_ratio" in blob  # missing key reported


def test_slo_check_ignores_non_api_services(tmp_path):
    services = _write(
        tmp_path / "services.yaml",
        "services:\n  - name: a-worker\n    type: worker\n  - name: a-job\n    type: job\n",
    )
    slo_dir = tmp_path / "slo"
    slo_dir.mkdir()
    assert cssf.check(services_path=services, slo_dir=slo_dir) == []


# --------------------------------------------------------------------- check_runbook_links failures


def test_runbook_check_flags_dangling_reference(tmp_path):
    rules = tmp_path / "docs" / "sre" / "slo"
    rules.mkdir(parents=True)
    _write(
        rules / "fake.yaml",
        "runbook: docs/sre/runbooks/this-does-not-exist.md\n",
    )
    problems, scanned = crl.check(repo_root=tmp_path)
    assert scanned == 1
    assert any("this-does-not-exist.md" in p for p in problems)
