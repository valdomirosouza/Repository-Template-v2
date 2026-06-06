"""Unit tests for CodePreFlight — static analysis gate for agent-generated code.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 1 (SD3)
ADR:  ADR-0047
Issue: #32
"""

from __future__ import annotations

import pytest

from src.agents.code_pre_flight import CodePreFlight, CodePreFlightError


class TestSyntaxCheck:
    def test_invalid_syntax_fails(self) -> None:
        result = CodePreFlight.check("def foo(: pass")
        assert not result.passed
        assert any(f.check == "syntax" for f in result.findings)

    def test_valid_syntax_passes(self) -> None:
        result = CodePreFlight.check("x = 1 + 2\nprint(x)")
        assert result.passed

    def test_empty_string_passes(self) -> None:
        result = CodePreFlight.check("")
        assert result.passed


class TestForbiddenImports:
    def test_subprocess_import_blocked(self) -> None:
        result = CodePreFlight.check("import subprocess")
        assert not result.passed
        assert any(f.check == "forbidden_import" for f in result.findings)

    def test_socket_import_blocked(self) -> None:
        result = CodePreFlight.check("import socket")
        assert not result.passed

    def test_ctypes_import_blocked(self) -> None:
        result = CodePreFlight.check("import ctypes")
        assert not result.passed

    def test_importlib_import_blocked(self) -> None:
        result = CodePreFlight.check("import importlib")
        assert not result.passed

    def test_from_subprocess_import_blocked(self) -> None:
        result = CodePreFlight.check("from subprocess import run")
        assert not result.passed
        assert any(f.check == "forbidden_import" for f in result.findings)

    def test_safe_import_passes(self) -> None:
        result = CodePreFlight.check("import json\nimport math\nimport os.path")
        assert result.passed

    def test_multiple_forbidden_imports_all_reported(self) -> None:
        result = CodePreFlight.check("import subprocess\nimport socket")
        assert not result.passed
        assert len([f for f in result.findings if f.check == "forbidden_import"]) == 2


class TestForbiddenCalls:
    def test_eval_call_blocked(self) -> None:
        result = CodePreFlight.check("eval('1 + 1')")
        assert not result.passed
        assert any(f.check == "forbidden_call" for f in result.findings)

    def test_exec_call_blocked(self) -> None:
        result = CodePreFlight.check("exec('print(1)')")
        assert not result.passed

    def test_dunder_import_call_blocked(self) -> None:
        result = CodePreFlight.check("__import__('os')")
        assert not result.passed

    def test_compile_call_blocked(self) -> None:
        result = CodePreFlight.check("compile('x = 1', '<str>', 'exec')")
        assert not result.passed

    def test_open_call_blocked(self) -> None:
        result = CodePreFlight.check("open('/etc/passwd', 'r')")
        assert not result.passed

    def test_safe_code_passes(self) -> None:
        result = CodePreFlight.check("data = [1, 2, 3]\nresult = sum(data)\nprint(result)")
        assert result.passed


class TestCheckOrRaise:
    def test_raises_code_pre_flight_error_on_violation(self) -> None:
        with pytest.raises(CodePreFlightError, match="pre-flight checks"):
            CodePreFlight.check_or_raise("import subprocess; subprocess.run(['rm', '-rf', '/'])")

    def test_no_raise_on_clean_code(self) -> None:
        CodePreFlight.check_or_raise("x = 2 ** 10\nprint(x)")  # must not raise

    def test_error_message_includes_finding_count(self) -> None:
        with pytest.raises(CodePreFlightError, match=r"\d+ finding"):
            CodePreFlight.check_or_raise("import subprocess\nimport socket")

    def test_error_message_includes_finding_details(self) -> None:
        with pytest.raises(CodePreFlightError, match="forbidden_import"):
            CodePreFlight.check_or_raise("import ctypes")


class TestFindingLineNumbers:
    def test_finding_includes_line_number(self) -> None:
        result = CodePreFlight.check("x = 1\nimport subprocess")
        assert not result.passed
        finding = next(f for f in result.findings if f.check == "forbidden_import")
        assert finding.line == 2

    def test_eval_finding_includes_line_number(self) -> None:
        result = CodePreFlight.check("y = 2\neval('y')")
        finding = next(f for f in result.findings if f.check == "forbidden_call")
        assert finding.line == 2
