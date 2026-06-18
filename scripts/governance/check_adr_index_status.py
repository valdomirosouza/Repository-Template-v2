#!/usr/bin/env python3
"""Fail if an ADR file's Status disagrees with its row in the ADR index (audit follow-up).

`docs/adr/README.md` is the authoritative ADR lookup. When an ADR file header says `Proposed`
but the index advertises `Accepted` (or vice-versa), consumers treat an unratified decision as
binding — exactly the drift the 2026-06-16 ADR audit found on ADR-0007/0067/0068/0069.

This gate parses each `docs/adr/ADR-NNNN-*.md` header `**Status:**` line and the matching row in
the index table, then compares the *primary* status token (case-insensitive, ignoring trailing
qualifiers like "Accepted (extended by ADR-0058)"). It also reports ADRs missing from the index
and index rows with no file on disk.

Usage:
    python3 scripts/governance/check_adr_index_status.py            # blocking (exit 1 on mismatch)
    python3 scripts/governance/check_adr_index_status.py --report   # report-mode (always exit 0)

Exit 0 = every ADR's status agrees with the index; exit 1 = at least one mismatch (unless --report).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ADR_DIR = _REPO_ROOT / "docs" / "adr"
_INDEX = _ADR_DIR / "README.md"

_KNOWN_STATUSES = {"draft", "proposed", "accepted", "deprecated", "superseded", "rejected"}
_FILE_RE = re.compile(r"^ADR-(\d{4})-.*\.md$")
# Matches both the prose header (`**Status:** Accepted`) and the table header
# (`| **Status** | Accepted |`); the captured remainder is fed to _primary_status().
_STATUS_LINE_RE = re.compile(r"\*\*Status:?\*\*(.*)")
# An index row: | [ADR-0007](ADR-0007-service-mesh.md) | Service Mesh | Accepted | 2026-05-29 |
_INDEX_ROW_RE = re.compile(r"\[ADR-(\d{4})\]\(")


def _primary_status(raw: str) -> str:
    """Lowercased first known status token in `raw` ('Accepted (extended ...)' -> 'accepted')."""
    words = [str(w).lower() for w in re.findall(r"[A-Za-z]+", raw)]
    for word in words:
        if word in _KNOWN_STATUSES:
            return word
    # fall back to the first word so genuinely-unknown values still surface as a mismatch
    return words[0] if words else ""


def _file_statuses(adr_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(adr_dir.glob("ADR-*.md")):
        m = _FILE_RE.match(path.name)
        if not m:
            continue  # e.g. ADR-TEMPLATE.md
        sm = _STATUS_LINE_RE.search(path.read_text(encoding="utf-8"))
        out[m.group(1)] = _primary_status(sm.group(1)) if sm else ""
    return out


def _index_statuses(index: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in index.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        m = _INDEX_ROW_RE.search(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        statuses = (_primary_status(c) for c in cells)
        out[m.group(1)] = next((s for s in statuses if s in _KNOWN_STATUSES), "")
    return out


def check(repo_root: Path = _REPO_ROOT) -> list[str]:
    """Return a list of problem strings; empty when file and index statuses all agree."""
    files = _file_statuses(repo_root / "docs" / "adr")
    index = _index_statuses(repo_root / "docs" / "adr" / "README.md")
    problems: list[str] = []
    for num, fstatus in sorted(files.items()):
        if num not in index:
            problems.append(f"ADR-{num}: present on disk but missing from the index (README.md)")
            continue
        istatus = index[num]
        if fstatus != istatus:
            problems.append(
                f"ADR-{num}: status mismatch — file says '{fstatus or '?'}', "
                f"index says '{istatus or '?'}'"
            )
    for num in sorted(set(index) - set(files)):
        problems.append(f"ADR-{num}: index row has no matching ADR-{num}-*.md file on disk")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        action="store_true",
        help="report-mode (ADR-0070): print problems but always exit 0",
    )
    args = parser.parse_args(argv)

    problems = check()
    if problems:
        stream = sys.stdout if args.report else sys.stderr
        label = "Report-mode" if args.report else "ERROR"
        print(f"{label}: ADR status/index disagreements found:", file=stream)
        for p in problems:
            print(f"  - {p}", file=stream)
        print(
            "\nReconcile the ADR file header `**Status:**` with its row in docs/adr/README.md.",
            file=stream,
        )
        return 0 if args.report else 1
    print(f"OK — all {len(_file_statuses(_ADR_DIR))} ADR statuses agree with the index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
