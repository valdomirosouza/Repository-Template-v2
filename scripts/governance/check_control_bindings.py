"""Control-binding governance gate (ADR-0061, RFC-0004).

Verifies that a PR DECLARES the controls required by the surfaces it touches. This
enforces *declaration discipline* — did the task bind the control? — NOT the correctness
of the control's implementation (explicit non-goal, ADR-0061).

The core (`evaluate`) is pure and offline: its inputs are the changed-file list, the diff
text, the declared bindings, and the two parsed config files. No network, no git, no clock.
A thin CLI wraps it; `--local` gathers inputs from `git` for convenience only.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

# A declared skill control looks like "<domain>/<name>"; ambient controls are "ADR-NNNN"
# or a named gate (e.g. "sbom-sca-gate").
_SKILL_RE = re.compile(r"\b([a-z][a-z0-9-]+/[a-z0-9][a-z0-9-]+)\b")
_ADR_RE = re.compile(r"\b(ADR-\d{3,4})\b")
_KNOWN_AMBIENT = {"sbom-sca-gate"}
_ALLOW_MARKER_RE = re.compile(
    r"#\s*control-binding:\s*ignore\s+(?P<id>[a-z0-9-]+)\s+reason=(?P<reason>.+)$"
)


@dataclass(frozen=True)
class Trigger:
    id: str
    description: str
    paths: tuple[str, ...] = ()
    content: tuple[str, ...] = ()
    requires_all: tuple[str, ...] = ()
    requires_any: tuple[str, ...] = ()
    requires_ambient: tuple[str, ...] = ()
    kind: str = "skill"
    conditional_on: str | None = None


@dataclass(frozen=True)
class Violation:
    code: str  # missing-control | budget | atomicity
    message: str


@dataclass
class Report:
    fired: list[str] = field(default_factory=list)
    exempt: list[str] = field(default_factory=list)
    suppressed: list[str] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    declared_skills: set[str] = field(default_factory=set)
    declared_ambient: set[str] = field(default_factory=set)
    rows: list[tuple[str, str, str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


MAX_SKILLS = 2
ATOMICITY_DOMAIN_LIMIT = 3


# --------------------------------------------------------------------------- parsing


def load_triggers(path: str | Path) -> list[Trigger]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    out: list[Trigger] = []
    for t in data.get("triggers", []):
        out.append(
            Trigger(
                id=t["id"],
                description=t.get("description", ""),
                paths=tuple(t.get("paths", [])),
                content=tuple(t.get("content", [])),
                requires_all=tuple(t.get("requires_all", [])),
                requires_any=tuple(t.get("requires_any", [])),
                requires_ambient=tuple(t.get("requires_ambient", [])),
                kind=t.get("kind", "skill"),
                conditional_on=t.get("conditional_on"),
            )
        )
    return out


def load_matrix(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def parse_declarations(text: str) -> tuple[set[str], set[str]]:
    """Extract declared (skills, ambient) from a `## Skills — load before executing` block.

    Falls back to scanning the whole text if the header is absent, so a PR body that lists
    bindings elsewhere still counts. Returns (skills, ambient_controls).
    """
    block = _extract_skills_block(text)
    scope = block if block is not None else text
    skills = {m.group(1) for m in _SKILL_RE.finditer(scope)}
    ambient = {m.group(1) for m in _ADR_RE.finditer(scope)}
    for token in _KNOWN_AMBIENT:
        if re.search(rf"\b{re.escape(token)}\b", scope):
            ambient.add(token)
    # Skill-shaped tokens never count as ambient and vice versa; nothing to reconcile.
    return skills, ambient


def _extract_skills_block(text: str) -> str | None:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*#{1,6}\s*Skills\b", line, re.IGNORECASE) and "load" in line.lower():
            start = i + 1
            break
    if start is None:
        return None
    out: list[str] = []
    for line in lines[start:]:
        if re.match(r"^\s*#{1,6}\s+\S", line):  # next heading ends the block
            break
        out.append(line)
    return "\n".join(out)


def added_lines(diff_text: str) -> list[str]:
    """Return added lines from a unified diff (strip the leading '+', skip '+++' headers)."""
    out: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return out


# --------------------------------------------------------------------------- matching


def _path_matches(globs: Iterable[str], changed_files: Iterable[str]) -> bool:
    files = list(changed_files)
    for g in globs:
        for f in files:
            if fnmatch.fnmatch(f, g) or fnmatch.fnmatch(f, f"**/{g}"):
                return True
    return False


def _content_matches(regexes: Iterable[str], lines: Iterable[str]) -> bool:
    patterns = list(regexes)
    if not patterns:
        return True  # no content filter → path match alone fires the trigger
    text_lines = list(lines)
    for pat in patterns:
        rx = re.compile(pat)
        if any(rx.search(line) for line in text_lines):
            return True
    return False


def _suppressed_ids(lines: Iterable[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in lines:
        m = _ALLOW_MARKER_RE.search(line)
        if m:
            found[m.group("id")] = m.group("reason").strip()
    return found


def _in_scope(matrix: dict[str, Any], key: str) -> bool:
    return bool(matrix.get("regulatory_scope", {}).get(key, {}).get("in_scope", False))


# --------------------------------------------------------------------------- core


def evaluate(
    *,
    changed_files: list[str],
    diff_text: str,
    declared_skills: set[str],
    declared_ambient: set[str],
    triggers: list[Trigger],
    matrix: dict[str, Any],
    atomic_exception: bool = False,
) -> Report:
    """Pure evaluation. Returns a Report (violations + summary rows)."""
    rep = Report(declared_skills=set(declared_skills), declared_ambient=set(declared_ambient))
    lines = added_lines(diff_text)
    suppressions = _suppressed_ids(lines)

    for trig in triggers:
        path_hit = _path_matches(trig.paths, changed_files)
        if not (path_hit and _content_matches(trig.content, lines)):
            continue

        if trig.id in suppressions:
            rep.suppressed.append(f"{trig.id} (reason={suppressions[trig.id]})")
            rep.rows.append((trig.id, _required_str(trig), "—", "SUPPRESSED"))
            continue

        if trig.conditional_on and not _in_scope(matrix, trig.conditional_on):
            rep.exempt.append(
                f"{','.join(trig.requires_ambient) or trig.id} "
                f"({trig.conditional_on} out of scope — applicability-matrix.yml)"
            )
            rep.rows.append((trig.id, _required_str(trig), "—", "EXEMPT"))
            continue

        rep.fired.append(trig.id)
        missing: list[str] = []

        for control in trig.requires_all:
            if control not in declared_skills:
                missing.append(control)
                rep.violations.append(
                    Violation(
                        "missing-control",
                        f"PR touches `{trig.id}` ({trig.description}) "
                        f"but does not declare `{control}`. "
                        "Declare it under '## Skills — load before executing' or split the task.",
                    )
                )
        if trig.requires_any and not (set(trig.requires_any) & declared_skills):
            missing.append("|".join(trig.requires_any))
            rep.violations.append(
                Violation(
                    "missing-control",
                    f"PR touches `{trig.id}` but declares none of "
                    f"{', '.join(f'`{c}`' for c in trig.requires_any)} (at least one required).",
                )
            )
        for control in trig.requires_ambient:
            if control not in declared_ambient:
                missing.append(control)
                rep.violations.append(
                    Violation(
                        "missing-control",
                        f"PR touches `{trig.id}` but does not declare ambient control `{control}`.",
                    )
                )

        declared_for_row = _declared_str(trig, declared_skills, declared_ambient)
        rep.rows.append(
            (
                trig.id,
                _required_str(trig),
                declared_for_row,
                "MISSING: " + ", ".join(missing) if missing else "OK",
            )
        )

    # Budget: count only declared *skill* controls.
    if len(declared_skills) > MAX_SKILLS:
        rep.violations.append(
            Violation(
                "budget",
                f"budget exceeded — {len(declared_skills)} skills declared (max {MAX_SKILLS}): "
                f"{', '.join(sorted(declared_skills))}. "
                "This change is not atomic. Split it into separate tasks/PRs.",
            )
        )

    # Atomicity smell: 3+ distinct trigger domains fired.
    if len(set(rep.fired)) >= ATOMICITY_DOMAIN_LIMIT:
        msg = (
            f"atomicity smell — {len(set(rep.fired))} control domains fired "
            f"({', '.join(sorted(set(rep.fired)))}). This change is likely not atomic; "
            "split it (ADR-0060)."
        )
        if atomic_exception:
            # Severity downgraded to warn; recorded but not a violation.
            rep.suppressed.append(f"atomicity (atomic-exception label): {msg}")
        else:
            rep.violations.append(Violation("atomicity", msg))

    return rep


def _required_str(trig: Trigger) -> str:
    parts = list(trig.requires_all)
    if trig.requires_any:
        parts.append("(" + " or ".join(trig.requires_any) + ")")
    parts.extend(trig.requires_ambient)
    return ", ".join(parts) or "—"


def _declared_str(trig: Trigger, skills: set[str], ambient: set[str]) -> str:
    relevant = set(trig.requires_all) | set(trig.requires_any) | set(trig.requires_ambient)
    have = sorted((relevant & skills) | (relevant & ambient))
    return ", ".join(have) or "—"


# --------------------------------------------------------------------------- rendering / CLI


def render(rep: Report) -> str:
    out: list[str] = []
    out.append("Control-binding gate — fired triggers:")
    if rep.rows:
        out.append(f"  {'trigger':<26}{'required':<48}{'declared':<32}status")
        for tid, req, decl, status in rep.rows:
            out.append(f"  {tid:<26}{req:<48}{decl:<32}{status}")
    else:
        out.append("  (no control triggers fired)")
    for ex in rep.exempt:
        out.append(f"  EXEMPT: {ex}")
    for sup in rep.suppressed:
        out.append(f"  SUPPRESSED: {sup}")
    for v in rep.violations:
        out.append(f"✗ control-binding [{v.code}]: {v.message}")
    out.append("")
    out.append("RESULT: PASS" if rep.ok else f"RESULT: FAIL ({len(rep.violations)} violation(s))")
    return "\n".join(out)


def _read(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _git(args: list[str]) -> str:
    # Fixed argv (no shell), `git` from PATH, local-only --local convenience; no untrusted input.
    proc = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description="Control-binding governance gate (ADR-0061).")
    ap.add_argument("--changed-files", help="file with newline-separated changed paths (or '-')")
    ap.add_argument("--diff", help="file with unified diff text (or '-')")
    ap.add_argument("--declared", help="file containing the declarations / PR body")
    ap.add_argument("--declared-text", help="declarations as an inline string")
    ap.add_argument("--triggers", default=str(repo_root / ".github/control-triggers.yml"))
    ap.add_argument("--matrix", default=str(repo_root / "docs/governance/applicability-matrix.yml"))
    ap.add_argument("--atomic-exception", action="store_true", help="downgrade atomicity to warn")
    ap.add_argument("--local", action="store_true", help="gather changed files/diff from git")
    ap.add_argument("--base", default="main", help="base ref for --local (default: main)")
    args = ap.parse_args(argv)

    if args.local:
        rng = f"origin/{args.base}...HEAD"
        changed = [f for f in _git(["diff", "--name-only", rng]).splitlines() if f]
        diff_text = _git(["diff", rng])
    else:
        changed = [f for f in _read(args.changed_files).splitlines() if f.strip()]
        diff_text = _read(args.diff) if args.diff else ""

    declared_raw = (
        args.declared_text if args.declared_text else _read(args.declared) if args.declared else ""
    )
    skills, ambient = parse_declarations(declared_raw)

    rep = evaluate(
        changed_files=changed,
        diff_text=diff_text,
        declared_skills=skills,
        declared_ambient=ambient,
        triggers=load_triggers(args.triggers),
        matrix=load_matrix(args.matrix),
        atomic_exception=args.atomic_exception,
    )
    print(render(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
