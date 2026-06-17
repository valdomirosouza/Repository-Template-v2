#!/usr/bin/env python3
"""Fail if an ADR/RFC cross-reference link points at a file that does not exist (audit follow-up).

ADRs and RFCs link to each other by relative filename (e.g. `[ADR-0018](ADR-0018-...md)`). When an
ADR is renamed, the link slugs that referenced it silently rot. The 2026-06-16 audit found 8 broken
ADR-link slugs across 5 files (more than a manual sample caught) — a class of error a one-line gate
prevents from ever recurring.

This gate scans every `docs/adr/*.md` and `docs/change-management/rfc/*.md`, extracts each Markdown
link whose target is an `ADR-NNNN-*.md` or `RFC-NNNN-*.md` file (ignoring http(s) URLs and pure
anchors), resolves it relative to the linking file's directory, and verifies it exists. A target
that resolves only under `/deprecated/` is reported as a WARNING (archived historical input — see
docs/adr/EXTERNAL-INPUTS.md), not a hard failure.

Usage:
    python3 scripts/governance/check_doc_references.py            # blocking (exit 1 on broken link)
    python3 scripts/governance/check_doc_references.py --report   # report-mode (always exit 0)

Exit 0 = every ADR/RFC link resolves; exit 1 = at least one dangling link (unless --report).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_DIRS = ("docs/adr", "docs/change-management/rfc")

# A Markdown link to an ADR/RFC file: capture the link target (may include a relative path prefix).
_LINK_RE = re.compile(r"\]\((?!https?://)([^)#]*?(?:ADR|RFC)-\d{4}[^)#]*?\.md)(?:#[^)]*)?\)")


def check(repo_root: Path = _REPO_ROOT) -> tuple[list[str], list[str], int]:
    """Return (errors, warnings, links_scanned)."""
    errors: list[str] = []
    warnings: list[str] = []
    scanned = 0
    for rel_dir in _SOURCE_DIRS:
        src_dir = repo_root / rel_dir
        if not src_dir.is_dir():
            continue
        for source in sorted(src_dir.glob("*.md")):
            rel_source = source.relative_to(repo_root)
            for i, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
                for target in _LINK_RE.findall(line):
                    scanned += 1
                    resolved = (source.parent / target).resolve()
                    if resolved.is_file():
                        continue
                    # second chance: archived historical inputs under /deprecated/
                    deprecated = repo_root / "deprecated" / Path(target).name
                    if deprecated.is_file():
                        warnings.append(
                            f"{rel_source}:{i}: link resolves only under /deprecated/ -> {target} "
                            f"(see docs/adr/EXTERNAL-INPUTS.md)"
                        )
                    else:
                        errors.append(f"{rel_source}:{i}: dangling ADR/RFC link -> {target}")
    return errors, warnings, scanned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        action="store_true",
        help="report-mode (ADR-0070): print problems but always exit 0",
    )
    args = parser.parse_args(argv)

    errors, warnings, scanned = check()
    for w in warnings:
        print(f"::warning:: {w}")
    if errors:
        stream = sys.stdout if args.report else sys.stderr
        label = "Report-mode" if args.report else "ERROR"
        print(f"{label}: dangling ADR/RFC cross-reference link(s) found:", file=stream)
        for e in errors:
            print(f"  - {e}", file=stream)
        print("\nFix the link slug to match the current filename, or add the target.", file=stream)
        return 0 if args.report else 1
    print(f"OK — all {scanned} ADR/RFC cross-reference link(s) resolve ({len(warnings)} archived).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
