"""Test-integrity governance gate (ADR-0065).

Enforces the test invariants that *coverage cannot see* — coverage is a quantity metric,
fully satisfiable by adding weak tests while gutting strong ones. This gate guards integrity:

  1. **No silent test-count decrease.** A drop in the total (or per-marker) test count vs the
     committed baseline fails the PR unless justified with a `TEST-WAIVER: <reason>` line.
  2. **No unjustified skip / xfail.** A newly *added* `@pytest.mark.skip|xfail|skipif`,
     `pytest.skip(...)`, or `@unittest.skip` without a rationale (`reason=`, a string argument,
     or an inline `#` comment) fails the PR.

The RED-before-GREEN and test-co-location invariants (ADR-0065) are review-time rules documented
in `skills/engineering/testing-strategy.md`; this gate enforces the two that are machine-checkable.

The core (`evaluate`) is pure and offline: its inputs are the before/after test counts, the diff
text, and the waiver text. No network, no clock. `count_tests` statically analyses the tree with
`ast` (no pytest collection, so it runs without the test dependencies installed). A thin CLI wraps
it; `--local` gathers the diff and baseline from git for convenience.

Repo conventions: pure-Python, stdlib only, Python 3.13 (`pyproject.toml` `requires-python>=3.13`).

Spec/ADR: ADR-0065 (test-integrity invariants). Sibling of `check_control_bindings.py` (ADR-0061).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Known pytest markers (mirrors pyproject.toml [tool.pytest.ini_options] markers). A test counts
# toward every known marker it carries; tests with no known marker count as "unmarked".
KNOWN_MARKERS = (
    "unit",
    "integration",
    "security",
    "chaos",
    "abuse_case",
    "model_contract",
    "e2e",
    "benchmark",
)

_WAIVER_RE = re.compile(r"TEST-WAIVER:\s*(?P<reason>.+)$")
# Skip/xfail surfaces we treat as suppressing a test.
_SKIP_RE = re.compile(
    r"(@pytest\.mark\.(?:skip|skipif|xfail)|pytest\.(?:skip|xfail)\s*\(|@unittest\.skip)"
)


# --------------------------------------------------------------------------- data


@dataclass(frozen=True)
class TestCounts:
    total: int
    per_marker: dict[str, int]

    def to_json(self) -> dict[str, object]:
        return {"total": self.total, "per_marker": dict(sorted(self.per_marker.items()))}

    @staticmethod
    def from_json(data: dict[str, object]) -> TestCounts:
        per = {str(k): int(v) for k, v in dict(data.get("per_marker", {})).items()}  # type: ignore[arg-type]
        return TestCounts(total=int(data["total"]), per_marker=per)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Violation:
    code: str  # test-count-drop | unjustified-skip
    message: str


@dataclass
class Report:
    before: TestCounts
    after: TestCounts
    violations: list[Violation] = field(default_factory=list)
    waivers: list[str] = field(default_factory=list)
    skips_flagged: list[str] = field(default_factory=list)
    drops: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


# --------------------------------------------------------------------------- static analysis


def _marker_names(node: ast.expr) -> list[str]:
    """Extract marker names from a `pytest.mark.X` / `pytest.mark.X(...)` expression."""
    if isinstance(node, ast.Call):
        return _marker_names(node.func)
    # pytest.mark.<name> → Attribute(attr=<name>, value=Attribute(attr='mark', value=Name(...)))
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
        if node.value.attr == "mark":
            return [node.attr]
    return []


def _markers_from_assign(value: ast.expr) -> list[str]:
    """`pytestmark = pytest.mark.X` or `pytestmark = [pytest.mark.X, ...]`."""
    if isinstance(value, (ast.List, ast.Tuple)):
        out: list[str] = []
        for elt in value.elts:
            out.extend(_marker_names(elt))
        return out
    return _marker_names(value)


def _decorator_markers(decorators: list[ast.expr]) -> list[str]:
    out: list[str] = []
    for dec in decorators:
        out.extend(_marker_names(dec))
    return out


def count_tests_in_source(source: str) -> tuple[int, dict[str, list[str]]]:
    """Return (test_count, {marker: [test_names]}) for one module's source.

    A "test" is a top-level or class-nested function whose name starts with `test`.
    Each test's marker set = module-level `pytestmark` + enclosing-class + own decorators
    (intersected with KNOWN_MARKERS; "unmarked" if none match).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0, {}

    module_markers: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "pytestmark":
                    module_markers = _markers_from_assign(stmt.value)

    total = 0
    by_marker: dict[str, list[str]] = {}

    def record(name: str, markers: list[str]) -> None:
        nonlocal total
        total += 1
        known = [m for m in markers if m in KNOWN_MARKERS]
        for m in known or ["unmarked"]:
            by_marker.setdefault(m, []).append(name)

    def is_test_fn(node: ast.AST) -> bool:
        return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        )

    for node in tree.body:
        if is_test_fn(node):
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            record(node.name, module_markers + _decorator_markers(node.decorator_list))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            class_markers = module_markers + _decorator_markers(node.decorator_list)
            for sub in node.body:
                if is_test_fn(sub):
                    assert isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                    record(
                        f"{node.name}::{sub.name}",
                        class_markers + _decorator_markers(sub.decorator_list),
                    )

    return total, by_marker


def count_tests(root: str | Path) -> TestCounts:
    """Statically count tests under `root` (recursively, deterministic file order)."""
    root = Path(root)
    total = 0
    per_marker: dict[str, int] = {}
    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            t, by = count_tests_in_source(path.read_text(encoding="utf-8"))
            total += t
            for marker, names in by.items():
                per_marker[marker] = per_marker.get(marker, 0) + len(names)
    return TestCounts(total=total, per_marker=dict(sorted(per_marker.items())))


# --------------------------------------------------------------------------- diff parsing


def added_lines(diff_text: str) -> list[str]:
    """Added lines from a unified diff (strip leading '+', skip '+++' headers)."""
    return [
        ln[1:] for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++")
    ]


def parse_waivers(text: str) -> list[str]:
    return [
        m.group("reason").strip() for line in text.splitlines() if (m := _WAIVER_RE.search(line))
    ]


def _skip_is_justified(line: str) -> bool:
    """Justified if it has a reason= kwarg, a string argument, or an inline `#` comment."""
    if "reason=" in line or "reason =" in line:
        return True
    if "#" in line and line.split("#", 1)[1].strip():  # inline comment carrying a rationale
        return True
    # A positional string argument, e.g. pytest.skip("not on CI") or @pytest.mark.xfail("…").
    return bool(re.search(r"\(\s*[furb]*['\"]", line))


def find_added_skips(diff_text: str) -> list[tuple[str, bool]]:
    """Return (line, justified) for every added line introducing a skip/xfail surface."""
    out: list[tuple[str, bool]] = []
    for line in added_lines(diff_text):
        if _SKIP_RE.search(line):
            out.append((line.strip(), _skip_is_justified(line)))
    return out


# --------------------------------------------------------------------------- core


def evaluate(
    *,
    before: TestCounts,
    after: TestCounts,
    diff_text: str,
    waiver_text: str,
) -> Report:
    """Pure evaluation. Returns a Report (violations + summary)."""
    rep = Report(before=before, after=after)
    rep.waivers = parse_waivers(waiver_text) + parse_waivers(diff_text)

    # (1) No silent test-count decrease (total + per-marker).
    drops: list[str] = []
    if after.total < before.total:
        drops.append(f"total {before.total} -> {after.total} (-{before.total - after.total})")
    for marker, n_before in sorted(before.per_marker.items()):
        n_after = after.per_marker.get(marker, 0)
        if n_after < n_before:
            drops.append(f"{marker} {n_before} -> {n_after} (-{n_before - n_after})")
    rep.drops = drops
    if drops:
        if rep.waivers:
            # Waived — recorded, not a violation.
            pass
        else:
            rep.violations.append(
                Violation(
                    "test-count-drop",
                    "test count decreased without justification: "
                    + "; ".join(drops)
                    + ". Add a `TEST-WAIVER: <reason>` line (PR body or diff) if the deletion is "
                    "intended, or restore the tests. Tests are the spec (ADR-0065).",
                )
            )

    # (2) No unjustified skip / xfail in added lines.
    for line, justified in find_added_skips(diff_text):
        if not justified:
            rep.skips_flagged.append(line)
            rep.violations.append(
                Violation(
                    "unjustified-skip",
                    f'new skip/xfail added without a rationale: `{line}`. Add `reason="…"` or an '
                    "inline `# why` comment (ADR-0065 — no silent disabling of assertions).",
                )
            )

    return rep


# --------------------------------------------------------------------------- rendering / CLI


def render(rep: Report) -> str:
    out: list[str] = ["Test-integrity gate (ADR-0065):"]
    out.append(f"  total: {rep.before.total} → {rep.after.total}")
    if rep.drops:
        out.append(f"  drops: {'; '.join(rep.drops)}")
    for w in rep.waivers:
        out.append(f"  WAIVER: {w}")
    for s in rep.skips_flagged:
        out.append(f"  SKIP-FLAGGED: {s}")
    for v in rep.violations:
        out.append(f"✗ test-integrity [{v.code}]: {v.message}")
    out.append("")
    out.append("RESULT: PASS" if rep.ok else f"RESULT: FAIL ({len(rep.violations)} violation(s))")
    return "\n".join(out)


def _read(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _git(args: list[str]) -> str:
    # Fixed argv (no shell), `git` from PATH; local-only convenience; no untrusted input.
    proc = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    default_baseline = repo_root / "tests" / ".test-integrity-baseline.json"
    ap = argparse.ArgumentParser(description="Test-integrity governance gate (ADR-0065).")
    ap.add_argument("--root", default=str(repo_root / "tests"), help="test tree to count")
    ap.add_argument("--baseline", default=str(default_baseline), help="committed baseline JSON")
    ap.add_argument(
        "--update-baseline", action="store_true", help="rewrite the baseline from the tree and exit"
    )
    ap.add_argument("--diff", help="file with unified diff text (or '-')")
    ap.add_argument("--waiver-text", help="declarations / PR body containing TEST-WAIVER lines")
    ap.add_argument(
        "--local", action="store_true", help="gather the diff from git (origin/<base>...HEAD)"
    )
    ap.add_argument("--base", default="main", help="base ref for --local (default: main)")
    args = ap.parse_args(argv)

    after = count_tests(args.root)

    if args.update_baseline:
        Path(args.baseline).write_text(
            json.dumps(after.to_json(), indent=2) + "\n", encoding="utf-8"
        )
        print(f"Baseline updated: {args.baseline} (total={after.total})")
        return 0

    baseline_path = Path(args.baseline)
    if baseline_path.exists():
        before = TestCounts.from_json(json.loads(baseline_path.read_text(encoding="utf-8")))
    else:
        # First run: no baseline yet — adopt current as baseline, cannot detect a drop.
        before = after
        print(f"note: no baseline at {args.baseline}; run with --update-baseline to create it.")

    if args.local:
        diff_text = _git(["diff", f"origin/{args.base}...HEAD"])
    else:
        diff_text = _read(args.diff) if args.diff else ""

    waiver_text = _read(args.waiver_text) if args.waiver_text else ""

    rep = evaluate(before=before, after=after, diff_text=diff_text, waiver_text=waiver_text)
    print(render(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
