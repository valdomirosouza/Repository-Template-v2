#!/usr/bin/env python3
"""Fail if canary / error-budget thresholds are hard-coded in workflow YAML (ADR-0073).

SLO-driven canary thresholds live in `docs/sre/slo/<service>.yaml` and are read by the production
workflow at runtime (via yq). A numeric error-rate / p99 / error-budget threshold baked into a
workflow is exactly the divergence ADR-0073 removes: the gate and the SLO can silently disagree.
This anti-regression lint flags any such literal.

A line is flagged when it both (a) mentions a threshold metric (error rate, p99/p95 latency, error
budget, saturation) and (b) compares it against a numeric literal (`<`, `>`, `<=`, `>=` followed by
a number). PromQL quantile arguments (`histogram_quantile(0.99, ...)`) and comments are ignored —
they are not threshold comparisons.

Usage:
    python3 scripts/governance/check_slo_thresholds.py            # scan .github/workflows/*.yml
    python3 scripts/governance/check_slo_thresholds.py --path .github/workflows/cd-production.yml

Exit 0 = no hard-coded thresholds; exit 1 = at least one (use as a CI gate).
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_GLOB = ".github/workflows/*.yml"

# (a) a threshold metric is named on the line
_METRIC = re.compile(
    r"(?i)(error[_ ]?rate|\ber\b|p99|p95|latency|error[_ ]?budget|\bbudget\b|saturation)"
)
# (b) a comparison operator immediately followed by a numeric literal (the actual threshold)
_COMPARE = re.compile(r"[<>]=?\s*-?\d")
# Not SLO thresholds: PromQL quantile parameters (function args) and size/storage budgets
# (a "size budget (< 50 KB)" is bytes, not an error/latency SLO). Ignore these lines.
_ALLOW = re.compile(r"(?i)(histogram_quantile|\b(?:KB|MB|GB|TB|bytes?)\b)")


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line_no, line) for every line that hard-codes a threshold comparison."""
    hits: list[tuple[int, str]] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _ALLOW.search(line):
            continue
        if _METRIC.search(line) and _COMPARE.search(line):
            hits.append((i, raw.rstrip()))
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", action="append", help="workflow file(s); default: all workflows")
    args = ap.parse_args(argv)

    paths = args.path or sorted(glob.glob(str(_REPO_ROOT / _DEFAULT_GLOB)))
    if not paths:
        print(f"ERROR: no workflow files found ({_DEFAULT_GLOB})", file=sys.stderr)
        return 1

    findings: list[str] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            return 1
        try:
            rel = str(path.relative_to(_REPO_ROOT))
        except ValueError:
            rel = p
        for line_no, line in scan_text(path.read_text(encoding="utf-8")):
            findings.append(f"{rel}:{line_no}: {line.strip()}")

    if findings:
        print(
            "Hard-coded canary/error-budget threshold(s) found in workflow YAML (ADR-0073):",
            file=sys.stderr,
        )
        for f in findings:
            print(f"  - {f}", file=sys.stderr)
        print(
            "\nMove the threshold into docs/sre/slo/<service>.yaml and read it at runtime (yq).",
            file=sys.stderr,
        )
        return 1
    print(f"OK — no hard-coded canary thresholds in {len(paths)} workflow file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
