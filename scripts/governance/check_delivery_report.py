"""Validate a /deliver FINAL-REPORT against the spec registry (W13-T6, issue #371).

The FINAL-REPORT's requirement-traceability table used to be agent-authored prose in the
gitignored ``reports/`` sandbox. CODE-mode reports now live under ``docs/delivery/<SPEC-ID>/``
(tracked) and this script checks the rows a machine can check:

  D1  the run header names a spec id that exists in ``docs/governance/spec-registry.json``
  D2  every ``ADR-NNNN`` cited in the traceability table has a file in ``docs/adr/``
  D3  every relative ``Evidence`` path in the table exists (``logs/…`` resolved against the
      report directory; repo paths against the repo root)
  D4  the Ambiguity ledger has no ``blocking`` open question and no ``open`` assumption whose
      resolve-by phase is ≤ the last phase the report marks PASS

Usage: ``python scripts/governance/check_delivery_report.py docs/delivery/SPEC-FEAT-001/FINAL-REPORT.md``
Exit codes: 0 clean, 1 violations, 2 unreadable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_JSON = REPO_ROOT / "docs" / "governance" / "spec-registry.json"
_SPEC_ID = re.compile(r"\b(SPEC-[A-Z0-9]{2,6}-\d{3})\b")
_ADR = re.compile(r"\bADR-(\d{4})\b")
_PATH = re.compile(r"`([A-Za-z0-9_./-]+\.[a-z]{1,5})`")
_PHASE_PASS = re.compile(r"^\|\s*(\d+)\s*\|[^|]*\|\s*\**PASS\**", re.M)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _section(text: str, title_re: str) -> str:
    m = re.search(rf"^##+\s*{title_re}.*?$(.*?)(?=^##+\s|\Z)", text, re.M | re.S | re.I)
    return m.group(1) if m else ""


def evaluate(report_path: Path, repo_root: Path = REPO_ROOT) -> Report:
    rep = Report()
    text = report_path.read_text(encoding="utf-8", errors="replace")
    registry = json.loads((repo_root / "docs" / "governance" / "spec-registry.json").read_text())
    known_ids = {s["id"] for s in registry.get("specs", [])}
    adrs = {p.name[4:8] for p in (repo_root / "docs" / "adr").glob("ADR-*.md")}

    # D1
    header = text[:2000]
    ids = set(_SPEC_ID.findall(header))
    if not ids:
        rep.errors.append("D1 run header names no SPEC-<DOMAIN>-NNN id")
    for sid in sorted(ids - known_ids):
        rep.errors.append(f"D1 spec id {sid} is not in docs/governance/spec-registry.json")

    # D2 / D3 — traceability table
    table = _section(text, r"(?:\d+\.\s*)?Requirement.traceability")
    if not table.strip():
        rep.errors.append("D2 no 'Requirement-traceability' section found")
    for n in sorted(set(_ADR.findall(table))):
        if n not in adrs:
            rep.errors.append(f"D2 traceability cites ADR-{n} which has no file")
    for path in sorted(set(_PATH.findall(table))):
        cand = (report_path.parent / path) if path.startswith("logs/") else (repo_root / path)
        if not cand.exists():
            rep.errors.append(f"D3 evidence path does not exist -> {path}")

    # D4 — ambiguity ledger
    passed = [int(p) for p in _PHASE_PASS.findall(_section(text, r"(?:\d+\.\s*)?Summary"))]
    last_pass = max(passed) if passed else 0
    ledger = _section(text, r"(?:\d+\.\s*)?Ambiguity ledger")
    for row in ledger.splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0].lower() in {"phase", "---"} or cells[0].startswith("-"):
            continue
        phase, kind, item, _owner, resolve_by, status = cells[:6]
        if kind.lower().startswith("open") and status.lower().startswith("block"):
            rep.errors.append(f"D4 blocking open question unresolved: {item}")
        m = re.search(r"\d+", resolve_by)
        if (
            kind.lower().startswith("assum")
            and status.lower() == "open"
            and m
            and int(m.group()) <= last_pass
        ):
            rep.errors.append(f"D4 assumption still open past phase {m.group()}: {item}")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a /deliver FINAL-REPORT (W13-T6).")
    ap.add_argument("report")
    args = ap.parse_args(argv)
    path = Path(args.report)
    if not path.exists():
        print(f"::error::{path} not found")
        return 2
    rep = evaluate(path)
    for e in rep.errors:
        print(f"::error::{e}")
    print("RESULT: PASS" if rep.ok else f"RESULT: FAIL ({len(rep.errors)} violation(s))")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
