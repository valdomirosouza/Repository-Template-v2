#!/usr/bin/env python3
"""Fail if a source file makes outbound HTTP requests without the SSRF allow-list (OWASP A10).

Server-side requests to user- or LLM-influenced URLs are an SSRF vector (CLAUDE.md §3.2 A10). Every
HTTP-client boundary must validate its target via ``src/shared/url_allowlist.validate_outbound_url``
(or ``is_outbound_url_allowed``). This lint flags any ``src/`` file that imports an outbound HTTP
library (``httpx`` / ``aiohttp`` / ``requests`` / ``urllib.request``) but does not reference the
allow-list helper.

Escape hatch: a file that genuinely needs no validation may carry a ``# ssrf-ok: <reason>`` comment.

Usage:
    python3 scripts/governance/check_outbound_urls.py            # scan src/
    python3 scripts/governance/check_outbound_urls.py --root src

Exit 0 = clean; exit 1 = an unguarded outbound-HTTP boundary (use as a CI gate).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ROOT = "src"

# Import of an outbound HTTP client library.
_HTTP_IMPORT = re.compile(
    r"^\s*(?:import\s+(?:httpx|aiohttp|requests)\b"
    r"|from\s+(?:httpx|aiohttp|requests)\b"
    r"|import\s+urllib\.request\b"
    r"|from\s+urllib\.request\b)",
    re.MULTILINE,
)
_GUARD_REF = re.compile(r"\b(?:validate_outbound_url|is_outbound_url_allowed)\b")
_WAIVER = re.compile(r"#\s*ssrf-ok:\s*\S+")

# This module defines the guard; it is exempt from requiring itself.
_EXEMPT = {"shared/url_allowlist.py"}


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = str(path.relative_to(root))
        if rel in _EXEMPT:
            continue
        text = path.read_text(encoding="utf-8")
        if not _HTTP_IMPORT.search(text):
            continue
        if _GUARD_REF.search(text) or _WAIVER.search(text):
            continue
        try:
            repo_rel = str(path.relative_to(_REPO_ROOT))
        except ValueError:
            repo_rel = str(path)
        findings.append(repo_rel)
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(_REPO_ROOT / _DEFAULT_ROOT))
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 1

    findings = scan(root)
    if findings:
        print(
            "Unguarded outbound-HTTP boundary — missing SSRF allow-list (OWASP A10):",
            file=sys.stderr,
        )
        for f in findings:
            print(f"  - {f}", file=sys.stderr)
        print(
            "\nValidate the target with src/shared/url_allowlist.validate_outbound_url(), "
            "or add a '# ssrf-ok: <reason>' waiver.",
            file=sys.stderr,
        )
        return 1
    print("OK — every outbound-HTTP boundary references the SSRF allow-list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
