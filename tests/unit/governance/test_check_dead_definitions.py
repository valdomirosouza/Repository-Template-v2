"""Unit tests for the dead-definition governance gate (W12-T5, issue #358)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_dead_definitions as dd  # noqa: E402

pytestmark = pytest.mark.unit

METRICS = """from prometheus_client import Counter, Gauge

LIVE = Counter("live_total", "used directly")
VIA_HELPER = Gauge("via_helper", "used through record()")
DEAD = Counter("dead_total", "nobody touches me")
ANNOTATED = Counter("annotated_total", "tracked")  # unwired: #999


def record(x: float) -> None:
    VIA_HELPER.set(x)


def never_called() -> None:
    DEAD.inc()
"""

CONFIG = """from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    used_field: int = 1
    dead_field: int = 2
    annotated_field: int = 3  # unwired: #998
    prop_backed: str = "x"

    @property
    def prop_backed_view(self) -> str:
        return self.prop_backed
"""

OTHER = """from src.observability.metrics import LIVE, record
from src.shared.config import settings

def go() -> None:
    LIVE.inc()
    record(1.0)
    print(settings.used_field)
"""


def _tree(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    (src / "observability").mkdir(parents=True)
    (src / "shared").mkdir(parents=True)
    (src / "observability" / "metrics.py").write_text(METRICS)
    (src / "shared" / "config.py").write_text(CONFIG)
    (src / "app.py").write_text(OTHER)
    return src


def test_detects_dead_metric_and_setting_and_honours_annotations(tmp_path: Path):
    src = _tree(tmp_path)
    rep = dd.evaluate(src, src / "observability" / "metrics.py", src / "shared" / "config.py")
    assert [m.split(": ")[-1] for m in rep.dead_metrics] == ["DEAD"]
    # prop_backed is consumed by a property inside config.py → live; dead_field is truly dead
    assert [s.split(": ")[-1] for s in rep.dead_settings] == ["dead_field"]
    assert rep.annotated == 2
    assert not rep.ok


def test_metric_reached_only_through_a_called_helper_is_live(tmp_path: Path):
    src = _tree(tmp_path)
    rep = dd.evaluate(src, src / "observability" / "metrics.py", src / "shared" / "config.py")
    assert "VIA_HELPER" not in "".join(rep.dead_metrics)


def test_render_marks_errors():
    rep = dd.Report(dead_metrics=["m.py:1: X"], dead_settings=[])
    out = dd.render(rep)
    assert "::error::D1" in out and "RESULT: FAIL" in out


def test_real_tree_is_clean():
    """Every metric and setting on main is wired or annotated with an issue (W12-T5)."""
    rep = dd.evaluate()
    assert rep.ok, dd.render(rep)
