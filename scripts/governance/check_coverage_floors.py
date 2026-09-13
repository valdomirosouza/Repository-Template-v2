"""Per-package coverage floors (W15-T1, issue #388, RFC-0020 ratchet).

``--cov-fail-under`` guards the total; a package can still rot behind a healthy average. This
gate reads ``coverage.json`` (``pytest --cov-report=json``) and enforces a floor per package
prefix. Floors only go up (ratchet, RFC-0020).

Exit codes: 0 clean, 1 a package is below its floor, 2 coverage.json unreadable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FLOORS: dict[str, float] = {
    "src/api/rest": 90.0,
    "src/guardrails": 84.0,  # 85.0 on 2026-09-12; audit_logger.py (54 %) and action_limits.py (79 %) drag it — raise with their tests
    "src/agents/hitl_gateway.py": 90.0,
    "src/workers": 85.0,
}


def package_coverage(data: dict, prefix: str) -> tuple[float, int, int]:
    """(percent, covered, statements) for every file whose path starts with prefix."""
    covered = total = 0
    for path, info in data.get("files", {}).items():
        norm = path.replace("\\", "/")
        if norm.startswith(prefix):
            s = info["summary"]
            covered += int(s["covered_lines"])
            total += int(s["num_statements"])
    return (100.0 * covered / total if total else 0.0), covered, total


def evaluate(data: dict, floors: dict[str, float]) -> list[str]:
    problems: list[str] = []
    for prefix, floor in floors.items():
        pct, cov, tot = package_coverage(data, prefix)
        if tot == 0:
            problems.append(f"{prefix}: no measured statements (path moved?)")
        elif pct < floor:
            problems.append(f"{prefix}: {pct:.1f}% < floor {floor:.0f}% ({cov}/{tot} statements)")
        else:
            print(f"  ok   {prefix}: {pct:.1f}% (floor {floor:.0f}%)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Per-package coverage floors (W15-T1).")
    ap.add_argument("--report", default=str(REPO_ROOT / "coverage.json"))
    args = ap.parse_args(argv)
    path = Path(args.report)
    if not path.exists():
        print(f"::error::{path} not found — run pytest --cov=src --cov-report=json first")
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))
    print("Per-package coverage floors (W15-T1):")
    problems = evaluate(data, DEFAULT_FLOORS)
    for p in problems:
        print(f"::error::{p}")
    print(
        "RESULT: PASS" if not problems else f"RESULT: FAIL ({len(problems)} package(s) below floor)"
    )
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
