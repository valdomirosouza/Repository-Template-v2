#!/usr/bin/env python3
"""Validate the single-source-of-truth project version across files.

`version.txt` is authoritative. This check (CI-enforced) fails if:
  - `pyproject.toml` `version` disagrees with `version.txt`; or
  - `README.md`'s `**Version:** X` line references a stale framework version.

CLAUDE.md carries an independent *behavioral-contract* version (its own `Version:`),
which is deliberately NOT coupled to the framework release version and is excluded.

Spec:  Agentic-SDLC-Repository-Improvement-Directive.md §6
ADR:   ADR-0057 (repository hygiene)
Usage: python scripts/check_version_consistency.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_README_VERSION_RE = re.compile(r"\*\*Version:\*\*\s*([0-9]+\.[0-9]+\.[0-9]+)")


def check(root: Path = ROOT) -> list[str]:
    """Return a list of consistency errors (empty list == all consistent)."""
    errors: list[str] = []

    version_txt = (root / "version.txt").read_text().strip()

    pyproject = (root / "pyproject.toml").read_text()
    m = _PYPROJECT_VERSION_RE.search(pyproject)
    if not m:
        errors.append("pyproject.toml has no top-level version field")
    elif m.group(1) != version_txt:
        errors.append(
            f"pyproject.toml version ({m.group(1)}) != version.txt ({version_txt}) — "
            "version.txt is the single source of truth"
        )

    readme_path = root / "README.md"
    if readme_path.exists():
        rm = _README_VERSION_RE.search(readme_path.read_text())
        if rm and rm.group(1) != version_txt:
            errors.append(
                f"README.md **Version:** ({rm.group(1)}) != version.txt ({version_txt}) — "
                "update the README version badge/header"
            )

    return errors


def main() -> int:
    errors = check()
    if errors:
        for e in errors:
            print(f"::error::{e}")
        return 1
    print(f"Version consistency OK (version.txt = {(ROOT / 'version.txt').read_text().strip()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
