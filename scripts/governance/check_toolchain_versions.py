"""Toolchain-version consistency gate (W14-T2, issue #377).

``versions.yaml`` is the single source of truth. For every tool it lists ``consumers`` — files
and the exact pattern in which the pinned version must appear (``{v}`` is substituted). A
consumer that does not contain the pattern is drift: the file pins a different version, or the
pin moved. ``--print <tool> <minimum|pinned>`` lets shell scripts (doctor.sh, check-versions.sh)
read values without a YAML parser.

Exit codes: 0 clean, 1 drift, 2 unreadable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS = REPO_ROOT / "versions.yaml"


def load(path: Path = VERSIONS) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("versions.yaml must be a mapping of tool -> {minimum, pinned, consumers}")
    return data


def evaluate(data: dict, repo: Path = REPO_ROOT) -> list[str]:
    problems: list[str] = []
    for tool, spec in sorted(data.items()):
        pinned = str(spec.get("pinned", ""))
        if not pinned:
            problems.append(f"{tool}: no pinned version")
            continue
        for c in spec.get("consumers") or []:
            path, pattern = (
                repo / str(c["path"]),
                str(c["pattern"]).replace("{v}", re.escape(pinned)),
            )
            if not path.exists():
                problems.append(f"{tool}: consumer missing -> {c['path']}")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if not re.search(pattern, text, re.M):
                problems.append(
                    f"{tool}: {c['path']} does not pin {pinned} (expected /{c['pattern']}/ with v={pinned})"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Toolchain-version consistency gate (W14-T2).")
    ap.add_argument(
        "--print", nargs=2, metavar=("TOOL", "FIELD"), help="print versions.yaml[TOOL][FIELD]"
    )
    args = ap.parse_args(argv)
    try:
        data = load()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"::error::{exc}")
        return 2
    if args.print:
        tool, field = args.print
        value = (data.get(tool) or {}).get(field)
        if value is None:
            return 2
        print(value)
        return 0
    problems = evaluate(data)
    for p in problems:
        print(f"::error::{p}")
    print("RESULT: PASS" if not problems else f"RESULT: FAIL ({len(problems)} drift(s))")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
