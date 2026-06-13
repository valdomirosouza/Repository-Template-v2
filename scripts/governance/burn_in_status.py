#!/usr/bin/env python3
"""Compute a governance gate's burn-in progress from docs/governance/gate-lifecycle.md.

ADR-0070 graduates a report-mode gate to blocking only after a burn-in:
**>= 15 consecutive PR runs OR 14 calendar days, whichever comes first, with zero
false-positive failures** (a false positive resets the window). The lifecycle log is the
source of truth; this tool reads it and reports whether the exit criterion is MET.

It is read-only and stdlib-only. Use it before proposing a flip-to-blocking PR:

    python3 scripts/governance/burn_in_status.py                 # print status (exit 0)
    python3 scripts/governance/burn_in_status.py --require-met   # exit 2 if NOT met (precondition)
    python3 scripts/governance/burn_in_status.py --gate control-binding-gate

The log table is parsed per gate section, identified by an HTML-comment marker pair:

    <!-- BURN-IN-START: 2026-06-12 -->
    <!-- BURN-IN-TARGET: control-binding-gate -->
    | Date (UTC) | PR | Verdict | False positive? | Notes |
    | ...
    | 2026-06-13 | #210 | PASS | no | ... |

Real rows have a `#<n>` PR and a Verdict of PASS or FAIL. A row with False positive? == yes
resets the window (it and everything before it no longer count toward the streak).
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LOG = _REPO_ROOT / "docs/governance/gate-lifecycle.md"

RUNS_REQUIRED = 15
DAYS_REQUIRED = 14

_START_RE = re.compile(r"<!--\s*BURN-IN-START:\s*(\d{4}-\d{2}-\d{2})\s*-->")
_TARGET_RE = re.compile(r"<!--\s*BURN-IN-TARGET:\s*([a-z0-9-]+)\s*-->")
_PR_RE = re.compile(r"#(\d+)")
_YES = {"yes", "y", "true"}


class Row:
    __slots__ = ("false_positive", "notes", "pr", "verdict", "when")

    def __init__(self, when: date, pr: int, verdict: str, false_positive: bool, notes: str):
        self.when = when
        self.pr = pr
        self.verdict = verdict
        self.false_positive = false_positive
        self.notes = notes


def _today() -> date:
    return datetime.now().date()


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_section(text: str, gate: str) -> tuple[date | None, list[Row]]:
    """Return (start_date, rows) for the gate whose BURN-IN-TARGET matches `gate`."""
    lines = text.splitlines()
    start: date | None = None
    in_section = False
    rows: list[Row] = []
    pending_start: date | None = None

    for line in lines:
        m_start = _START_RE.search(line)
        if m_start:
            pending_start = datetime.strptime(m_start.group(1), "%Y-%m-%d").date()
            continue
        m_target = _TARGET_RE.search(line)
        if m_target:
            if m_target.group(1) == gate:
                in_section = True
                start = pending_start
            elif in_section:
                break  # a new gate section begins → stop
            continue
        if not in_section:
            continue
        # Within the target section: parse table rows. Stop at the next heading.
        if re.match(r"^\s*#{1,6}\s", line):
            break
        if not line.lstrip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) < 4:
            continue
        m_pr = _PR_RE.search(cells[1])
        verdict = cells[2].upper()
        if not m_pr or verdict not in {"PASS", "FAIL"}:
            continue  # header, separator, or placeholder (PR == "—") row
        try:
            when = datetime.strptime(cells[0], "%Y-%m-%d").date()
        except ValueError:
            continue
        fp = cells[3].lower() in _YES
        rows.append(Row(when, int(m_pr.group(1)), verdict, fp, cells[4] if len(cells) > 4 else ""))

    return start, rows


class BurnIn(TypedDict):
    runs: int
    days: int
    window_start: date
    last_fp_idx: int
    reset_count: int
    met: bool
    rule: str


def evaluate(start: date | None, rows: list[Row], today: date) -> BurnIn:
    """Compute window stats. Window begins at the later of `start` and the last FP reset."""
    rows_sorted = sorted(rows, key=lambda r: (r.when, r.pr))
    last_fp_idx = max((i for i, r in enumerate(rows_sorted) if r.false_positive), default=-1)
    window = rows_sorted[last_fp_idx + 1 :]
    window_start = start or (today)
    if last_fp_idx >= 0:
        # window restarts the day after the false positive
        fp_day = rows_sorted[last_fp_idx].when
        window_start = max(window_start, fp_day)
    runs = len(window)
    days = (today - window_start).days if window_start else 0
    no_fp = not any(r.false_positive for r in window)
    met = (runs >= RUNS_REQUIRED or days >= DAYS_REQUIRED) and no_fp
    return {
        "runs": runs,
        "days": days,
        "window_start": window_start,
        "last_fp_idx": last_fp_idx,
        "reset_count": sum(1 for r in rows_sorted if r.false_positive),
        "met": met,
        "rule": (
            "runs>=15"
            if runs >= RUNS_REQUIRED
            else ("days>=14" if days >= DAYS_REQUIRED else "neither")
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", default=str(_DEFAULT_LOG), help="path to gate-lifecycle.md")
    ap.add_argument("--gate", default="control-binding-gate", help="BURN-IN-TARGET to evaluate")
    ap.add_argument("--require-met", action="store_true", help="exit 2 if the criterion is NOT met")
    args = ap.parse_args(argv)

    path = Path(args.log)
    if not path.exists():
        print(f"ERROR: lifecycle log not found: {path}", file=sys.stderr)
        return 1
    start, rows = parse_section(path.read_text(encoding="utf-8"), args.gate)
    if start is None:
        print(
            f"ERROR: no BURN-IN-START / BURN-IN-TARGET '{args.gate}' section in {path}",
            file=sys.stderr,
        )
        return 1

    today = _today()
    s = evaluate(start, rows, today)
    status = "MET" if s["met"] else "NOT MET"
    print(f"Gate           : {args.gate}")
    print(f"Burn-in start  : {start}    (window start: {s['window_start']})")
    print(f"Today          : {today}")
    print(f"Clean runs     : {s['runs']} / {RUNS_REQUIRED}")
    print(f"Days elapsed   : {s['days']} / {DAYS_REQUIRED}")
    print(f"FP resets       : {s['reset_count']}")
    print(f"Exit criterion : {status}" + (f"  (via {s['rule']})" if s["met"] else ""))
    if not s["met"]:
        need_runs = max(0, RUNS_REQUIRED - s["runs"])
        need_days = max(0, DAYS_REQUIRED - s["days"])
        print(
            f"Remaining      : {need_runs} more clean run(s) OR {need_days} more day(s), "
            "zero new false positives"
        )
    else:
        print(
            "Next step      : open the flip-to-blocking PR (normal-change, HITL) — remove "
            "`continue-on-error` from the control-binding step in ci.yml; record this evidence."
        )

    if args.require_met and not s["met"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
