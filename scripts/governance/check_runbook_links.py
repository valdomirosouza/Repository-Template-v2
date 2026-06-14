#!/usr/bin/env python3
"""Fail if any referenced runbook path does not resolve to a file on disk (ADR-0033).

An alert that points at a non-existent runbook is worse than no link: on-call follows it mid-
incident and hits a 404. Runbooks live in two deliberate namespaces (ADR-0033, issue #195):

    docs/runbooks/        — incident-response runbooks (RB-NNN)
    docs/sre/runbooks/    — SRE operational runbooks (RB-SRE-NNN)

This gate does NOT force one canonical path (that would break the two-namespace design). It scans
the places that reference runbooks — SLO definitions and Prometheus alert rules — extracts every
`docs/(sre/)?runbooks/<file>.md` reference (whether a bare path or inside a GitHub blob URL), and
verifies each one exists. It catches both a typo'd filename and a runbook that was moved/renamed
without updating its referrers.

Usage:
    python3 scripts/governance/check_runbook_links.py

Exit 0 = every referenced runbook resolves; exit 1 = at least one dangling reference.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Sources that reference runbooks. Globs are resolved relative to the repo root.
_SOURCE_GLOBS = (
    "docs/sre/slo/*.yaml",
    "infrastructure/monitoring/prometheus/rules/*.yaml",
    "infrastructure/monitoring/prometheus/rules/*.yml",
)

# A runbook reference: a path under either runbook namespace ending in .md. Works whether the
# reference is a bare relative path (`docs/sre/runbooks/foo.md`) or embedded in a GitHub blob URL
# (`https://github.com/org/repo/blob/main/docs/runbooks/foo.md`) — we match the docs/... suffix.
_RUNBOOK_REF = re.compile(r"docs/(?:sre/)?runbooks/[A-Za-z0-9._-]+\.md")


def check(repo_root: Path = _REPO_ROOT) -> tuple[list[str], int]:
    """Return (problems, refs_scanned). `problems` is empty when every reference resolves."""
    problems: list[str] = []
    refs_scanned = 0
    for pattern in _SOURCE_GLOBS:
        for source in sorted(repo_root.glob(pattern)):
            text = source.read_text(encoding="utf-8")
            rel_source = source.relative_to(repo_root)
            for i, raw in enumerate(text.splitlines(), start=1):
                for ref in _RUNBOOK_REF.findall(raw):
                    refs_scanned += 1
                    if not (repo_root / ref).is_file():
                        problems.append(f"{rel_source}:{i}: dangling runbook reference -> {ref}")
    return problems, refs_scanned


def main(argv: list[str] | None = None) -> int:
    problems, scanned = check()
    if problems:
        print("Dangling runbook reference(s) found (ADR-0033):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "\nCreate the runbook or fix the reference. Namespaces: docs/runbooks/ (RB-NNN), "
            "docs/sre/runbooks/ (RB-SRE-NNN).",
            file=sys.stderr,
        )
        return 1
    print(f"OK — all {scanned} runbook reference(s) resolve to existing files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
