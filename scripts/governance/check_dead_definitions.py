"""Dead-definition governance gate (W12-T5, issue #358).

A Prometheus metric that is defined but never observed, or a ``Settings`` field that nothing
reads, is documentation that lies: dashboards and runbooks reference the metric, ``.env.example``
documents the setting, and neither does anything. The Seven-Axis Review (2026-09-12) counted
22 of ~40 metrics never incremented and several dead settings.

Rules:

  D1  every module-level ``NAME = Counter|Gauge|Histogram|Summary(...)`` in
      ``src/observability/metrics.py`` is referenced (by name) in at least one *other* file
      under ``src/`` — or the definition line carries ``# unwired: #<issue>``.
  D2  every field of ``class Settings`` in ``src/shared/config.py`` is referenced as
      ``settings.<field>`` / ``.<field>`` somewhere in ``src/`` outside ``config.py`` — or the
      field line carries ``# unwired: #<issue>``. A field consumed inside ``config.py`` itself
      (validator, derived property, cross-field check) counts as live.

A ``metrics.py`` helper (e.g. ``record_request``) that touches a metric counts as a reference
only if the helper itself is called from another file — otherwise both are dead together.

Exit codes: 0 = clean, 1 = at least one dead definition.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
METRICS = SRC / "observability" / "metrics.py"
CONFIG = SRC / "shared" / "config.py"

_METRIC_CTORS = {"Counter", "Gauge", "Histogram", "Summary", "Info", "Enum"}
_UNWIRED_RE = re.compile(r"#\s*unwired:\s*#\d+")


@dataclass
class Report:
    dead_metrics: list[str] = field(default_factory=list)
    dead_settings: list[str] = field(default_factory=list)
    annotated: int = 0

    @property
    def ok(self) -> bool:
        return not (self.dead_metrics or self.dead_settings)


# --------------------------------------------------------------------------- scanning


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:  # scanning a tree outside the repo (tests)
        return str(path)


def _src_files(src: Path) -> list[Path]:
    return [
        p for p in src.rglob("*.py") if "__pycache__" not in p.parts and "generated" not in p.parts
    ]


def _line_has_unwired(lines: list[str], lineno: int) -> bool:
    """Annotation on the definition line, or on a pure comment line directly above it."""
    if _UNWIRED_RE.search(lines[lineno - 1]):
        return True
    above = lines[lineno - 2].strip() if lineno >= 2 else ""
    return above.startswith("#") and bool(_UNWIRED_RE.search(above))


def metric_names(metrics_src: str) -> dict[str, int]:
    """{NAME: lineno} for module-level metric definitions."""
    tree = ast.parse(metrics_src)
    out: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            call = node.value
            if (
                isinstance(tgt, ast.Name)
                and isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id in _METRIC_CTORS
            ):
                out[tgt.id] = node.lineno
    return out


def helper_calls_in(metrics_src: str) -> dict[str, set[str]]:
    """{helper_function_name: {metric names it touches}} inside metrics.py."""
    tree = ast.parse(metrics_src)
    names = set(metric_names(metrics_src))
    out: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in names}
            if used:
                out[node.name] = used
    return out


def settings_fields(config_src: str) -> dict[str, int]:
    tree = ast.parse(config_src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            return {
                item.target.id: item.lineno
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            }
    return {}


# --------------------------------------------------------------------------- core


def evaluate(src: Path = SRC, metrics_path: Path = METRICS, config_path: Path = CONFIG) -> Report:
    rep = Report()
    metrics_src = _read(metrics_path)
    config_src = _read(config_path)
    metrics_lines = metrics_src.splitlines()
    config_lines = config_src.splitlines()

    others = [p for p in _src_files(src) if p not in (metrics_path, config_path)]
    corpus = "\n".join(_read(p) for p in others)

    # D1 — metrics
    names = metric_names(metrics_src)
    helpers = helper_calls_in(metrics_src)
    live_helpers = {h for h in helpers if re.search(rf"\b{re.escape(h)}\s*\(", corpus)}
    reached_via_helper = {m for h in live_helpers for m in helpers[h]}
    for name, lineno in sorted(names.items()):
        if _line_has_unwired(metrics_lines, lineno):
            rep.annotated += 1
            continue
        if re.search(rf"\b{re.escape(name)}\b", corpus) or name in reached_via_helper:
            continue
        rep.dead_metrics.append(f"{_rel(metrics_path)}:{lineno}: {name}")

    # D2 — settings. A field consumed inside config.py itself (a validator, a derived property
    # such as `llm_api_key`, a cross-field check) is live: only the definition line is excluded.
    for name, lineno in sorted(settings_fields(config_src).items()):
        if _line_has_unwired(config_lines, lineno):
            rep.annotated += 1
            continue
        if re.search(rf"\.{re.escape(name)}\b", corpus):
            continue
        internal = "\n".join(ln for i, ln in enumerate(config_lines, 1) if i != lineno)
        if re.search(rf"(self|values|info\.data)(\.|\[\")?{re.escape(name)}\b", internal):
            continue
        rep.dead_settings.append(f"{_rel(config_path)}:{lineno}: {name}")
    return rep


def render(rep: Report) -> str:
    out = [f"Dead-definition gate (W12-T5): {rep.annotated} annotated as unwired"]
    out += [
        f"::error::D1 metric defined but never observed outside metrics.py: {m}"
        for m in rep.dead_metrics
    ]
    out += [
        f"::error::D2 Settings field never read outside config.py: {s}" for s in rep.dead_settings
    ]
    out.append(
        "RESULT: PASS"
        if rep.ok
        else f"RESULT: FAIL ({len(rep.dead_metrics)} metric(s), {len(rep.dead_settings)} "
        "setting(s)) — wire it, delete it, or annotate `# unwired: #<issue>`"
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Dead-definition governance gate (W12-T5).")
    ap.add_argument("--src", default=str(SRC))
    args = ap.parse_args(argv)
    src = Path(args.src)
    rep = evaluate(src, src / "observability" / "metrics.py", src / "shared" / "config.py")
    print(render(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
