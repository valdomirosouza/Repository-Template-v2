"""Execute a ``harness/*.yml`` gate spec (W12-T8, issue #361, ADR-0037 amendment).

The five ``harness/*.yml`` files declare gates with ``command`` / ``blocking`` — the Claude Code
review-agent contract — but no workflow or Makefile target executed them, while the PR template
called them the authoritative gate list (fixed in W11-T7). This runner makes the declaration
real: it runs every gate's command in order, honours ``blocking``, and emits a GitHub-Actions
friendly summary. It is deliberately tiny and dependency-free (PyYAML only).

Usage::

    python scripts/governance/run_harness_spec.py harness/code-check.yml \\
        [--only lint,sast] [--dry-run]

Exit codes: 0 = every blocking gate passed (non-blocking failures are reported as warnings),
1 = at least one blocking gate failed, 2 = spec could not be parsed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class GateResult:
    name: str
    blocking: bool
    returncode: int
    seconds: float
    tail: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def load_gates(spec_path: Path) -> list[dict]:
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    gates = data.get("gates")
    if not isinstance(gates, list):
        raise ValueError(f"{spec_path}: no `gates:` list (is this a runnable harness spec?)")
    out = []
    for g in gates:
        if not isinstance(g, dict) or "name" not in g or "command" not in g:
            raise ValueError(f"{spec_path}: every gate needs `name` and `command`: {g!r}")
        out.append(g)
    return out


def run_gate(gate: dict, *, cwd: Path, dry_run: bool, timeout: int) -> GateResult:
    cmd = str(gate["command"]).strip()
    blocking = bool(gate.get("blocking", True))
    if dry_run:
        return GateResult(gate["name"], blocking, 0, 0.0, f"[dry-run] {cmd}")
    start = time.monotonic()
    proc = subprocess.run(  # noqa: S602 — the command comes from a repo-committed spec, by design
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "HARNESS_GATE": gate["name"]},
    )
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
    return GateResult(gate["name"], blocking, proc.returncode, time.monotonic() - start, tail)


def render(spec: Path, results: list[GateResult]) -> str:
    lines = [
        f"Harness spec: {spec.relative_to(REPO_ROOT) if spec.is_relative_to(REPO_ROOT) else spec}"
    ]
    for r in results:
        mark = "PASS" if r.passed else ("FAIL" if r.blocking else "WARN")
        lines.append(
            f"  [{mark}] {r.name} ({r.seconds:.1f}s){'' if r.blocking else ' non-blocking'}"
        )
        if r.tail.startswith("[dry-run]"):
            lines.append(f"      {r.tail}")
        if not r.passed:
            prefix = "::error::" if r.blocking else "::warning::"
            lines.append(f"{prefix}harness gate `{r.name}` failed (rc={r.returncode})")
            lines.extend(f"      {ln}" for ln in r.tail.splitlines())
    failed = [r for r in results if r.blocking and not r.passed]
    lines.append("RESULT: PASS" if not failed else f"RESULT: FAIL ({len(failed)} blocking gate(s))")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a harness/*.yml gate spec.")
    ap.add_argument("spec", help="path to harness/<name>.yml")
    ap.add_argument("--only", default="", help="comma-separated gate names to run")
    ap.add_argument("--skip", default="", help="comma-separated gate names to skip")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800, help="per-gate timeout (s)")
    args = ap.parse_args(argv)
    spec = Path(args.spec)
    try:
        gates = load_gates(spec)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"::error::{exc}")
        return 2
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    skip = {x.strip() for x in args.skip.split(",") if x.strip()}
    selected = [g for g in gates if (not only or g["name"] in only) and g["name"] not in skip]
    results = [
        run_gate(g, cwd=REPO_ROOT, dry_run=args.dry_run, timeout=args.timeout) for g in selected
    ]
    print(render(spec, results))
    return 0 if all(r.passed or not r.blocking for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
