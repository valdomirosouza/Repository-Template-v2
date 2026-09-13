"""Assertion-presence lint for tests (W15-T2, issue #389, ADR-0065).

A test that asserts nothing passes no matter what the code does. The Seven-Axis Review counted
29 such functions (2.2 %), several with names that promise a check they never make. This gate
walks every ``tests/**/test_*.py`` with ``ast`` and flags a test function whose body contains
none of:

  * an ``assert`` statement (anywhere in the body, including nested blocks)
  * ``pytest.raises`` / ``pytest.warns`` / ``pytest.fail`` / ``pytest.xfail`` / ``pytest.skip``
  * a mock assertion (``assert_called*``, ``assert_awaited*``, ``assert_not_*``, ``assert_any_*``)
  * ``self.assert*`` (unittest style)
  * a call to a helper whose name starts with ``assert_`` / ``check_`` / ``verify_`` / ``expect_``

Escape hatch: a ``# noassert: <reason>`` comment on the ``def`` line (for genuine "does not
raise" smoke tests) — it is counted and printed so reviewers see every use.

Exit codes: 0 clean, 1 at least one assertion-free test.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = REPO_ROOT / "tests"
_NOASSERT_RE = re.compile(r"#\s*noassert:\s*\S")
_PYTEST_CHECKS = {"raises", "warns", "fail", "xfail", "skip"}
_HELPER_PREFIXES = ("assert_", "check_", "verify_", "expect_", "validate_")


def _has_assertion(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            f = node.func
            name = (
                f.attr
                if isinstance(f, ast.Attribute)
                else (f.id if isinstance(f, ast.Name) else "")
            )
            if name.startswith("assert") or name.startswith(_HELPER_PREFIXES):
                return True
            if (
                isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id == "pytest"
            ):
                if f.attr in _PYTEST_CHECKS:
                    return True
        if isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and isinstance(ctx.func, ast.Attribute):
                    if ctx.func.attr in _PYTEST_CHECKS:
                        return True
    return False


def scan(root: Path = TESTS) -> tuple[list[str], list[str]]:
    """Return (violations, waived) as 'path:line: name' strings."""
    violations: list[str] = []
    waived: list[str] = []
    for path in sorted(root.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        for node in tree.body:  # pytest collects module-level tests and Test* class methods only
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                candidates.append(node)
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                candidates += [
                    n for n in node.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                ]
        for node in candidates:
            if node.name.startswith("test"):
                if _has_assertion(node):
                    continue
                rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
                entry = f"{rel}:{node.lineno}: {node.name}"
                # the waiver may sit on any signature line (formatters wrap long defs)
                first_body = node.body[0].lineno if node.body else node.lineno + 1
                signature = "\n".join(lines[node.lineno - 1 : first_body - 1])
                if _NOASSERT_RE.search(signature):
                    waived.append(entry)
                else:
                    violations.append(entry)
    return violations, waived


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assertion-presence lint for tests (W15-T2).")
    ap.add_argument("--root", default=str(TESTS))
    args = ap.parse_args(argv)
    violations, waived = scan(Path(args.root))
    print(f"Assertion-presence gate (W15-T2): {len(waived)} waived via `# noassert:`")
    for w in waived:
        print(f"  WAIVED {w}")
    for v in violations:
        print(f"::error::test asserts nothing: {v}")
    print(
        "RESULT: PASS"
        if not violations
        else f"RESULT: FAIL ({len(violations)} assertion-free test(s))"
    )
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
