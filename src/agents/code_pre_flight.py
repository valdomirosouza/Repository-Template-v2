"""Static pre-flight check for agent-generated code before sandbox execution.

Provides a defense-in-depth layer between LLM code generation and Docker sandbox
execution. Catches the most obvious attack vectors (forbidden imports, eval/exec)
using AST analysis — no subprocess required, runs in-process.

The sandbox (ADR-0016) provides runtime isolation; this module provides pre-execution
static gating. Both layers are required (defense-in-depth).

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 1 (SD3)
ADR:  ADR-0047
Issue: #32
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


class CodePreFlightError(Exception):
    """Raised when agent-generated code fails pre-flight static checks."""


@dataclass
class PreFlightFinding:
    """A single static analysis finding."""

    check: str
    detail: str
    line: int = 0


@dataclass
class PreFlightResult:
    """Aggregated result from all pre-flight checks."""

    passed: bool
    findings: list[PreFlightFinding] = field(default_factory=list)


class CodePreFlight:
    """AST-based static analyser for AI-generated Python code.

    Checks (in order):
      1. Syntax — code must parse cleanly.
      2. Forbidden imports — blocks modules that provide escape hatches from the sandbox.
      3. Forbidden calls — blocks direct invocations of eval, exec, __import__, compile.

    Usage::

        CodePreFlight.check(generated_code_string)  # raises CodePreFlightError on failure
    """

    # Modules that provide privilege-escalation paths even inside Docker network=none.
    FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
        {
            "subprocess",
            "socket",
            "ctypes",
            "importlib",
            "pty",
            "pdb",
            "multiprocessing",
            "concurrent.futures",
        }
    )

    # Built-in calls that allow arbitrary code execution or dynamic import.
    FORBIDDEN_CALLS: frozenset[str] = frozenset(
        {
            "eval",
            "exec",
            "__import__",
            "compile",
            "open",
        }
    )

    @classmethod
    def check(cls, code: str) -> PreFlightResult:
        """Run all static checks on the generated code string.

        Returns a `PreFlightResult` with `passed=True` if all checks pass.
        Does NOT raise — callers decide how to handle findings.
        Use `check_or_raise()` for the blocking gate.
        """
        findings: list[PreFlightFinding] = []

        # Check 1: syntax
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            findings.append(
                PreFlightFinding(
                    check="syntax",
                    detail=f"SyntaxError: {exc}",
                    line=exc.lineno or 0,
                )
            )
            return PreFlightResult(passed=False, findings=findings)

        # Check 2: forbidden imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in cls.FORBIDDEN_IMPORTS:
                        findings.append(
                            PreFlightFinding(
                                check="forbidden_import",
                                detail=f"Forbidden import: '{alias.name}'",
                                line=getattr(node, "lineno", 0),
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                module_root = (node.module or "").split(".")[0]
                if module_root in cls.FORBIDDEN_IMPORTS:
                    findings.append(
                        PreFlightFinding(
                            check="forbidden_import",
                            detail=f"Forbidden from-import: '{node.module}'",
                            line=getattr(node, "lineno", 0),
                        )
                    )

        # Check 3: forbidden calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name: str | None = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if func_name and func_name in cls.FORBIDDEN_CALLS:
                    findings.append(
                        PreFlightFinding(
                            check="forbidden_call",
                            detail=f"Forbidden call: '{func_name}()'",
                            line=getattr(node, "lineno", 0),
                        )
                    )

        return PreFlightResult(passed=len(findings) == 0, findings=findings)

    @classmethod
    def check_or_raise(cls, code: str) -> None:
        """Run all checks and raise CodePreFlightError if any finding is detected.

        This is the blocking gate used by sandbox_executor before invoking Docker.
        """
        result = cls.check(code)
        if not result.passed:
            summary = "; ".join(f"[{f.check}:{f.line}] {f.detail}" for f in result.findings)
            raise CodePreFlightError(
                f"Agent-generated code failed pre-flight checks "
                f"({len(result.findings)} finding(s)): {summary}"
            )
