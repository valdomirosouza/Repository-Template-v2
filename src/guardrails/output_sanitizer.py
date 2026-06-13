"""Output sanitization guardrail (OWASP LLM02 / LLM05).

Sanitizes **LLM-generated output** before it is rendered (HITL operator UI, logs) or could reach an
execution sink. This is the OUTPUT-side complement to ``prompt_injection_guard.py`` (which guards
the INPUT side). It **strengthens, never replaces** the injection guard (CLAUDE.md §3.2 LLM02).

Three transforms, each independently testable:

* ``strip_control_chars`` — remove C0/C1 control characters (except tab/newline/CR) that can spoof
  terminals, corrupt logs, or hide content.
* ``escape_markup`` — HTML-escape active markup for **render** contexts (operator UI, web logs).
* ``detect_code_exec_sinks`` — flag code-execution / active-content patterns (``eval(``,
  ``__import__``, ``<script>``, ``javascript:`` URIs, shell/template substitution, unsafe
  deserialization).

**Render vs execute (important):** markup-escaping is correct for *render* contexts but would
*corrupt* values that are later *executed* (e.g. a tool parameter). So ``sanitize_output`` defaults
to ``escape=False`` — it strips control chars and detects sinks (both safe for execute and render)
but does not escape; callers rendering to a UI pass ``escape=True`` (or use ``escape_markup``).
Detected sinks are reported so the orchestrator can route the action to HITL rather than execute it.

Spec: ``specs/ai/guardrails.md`` (Layer 5 — Output Sanitizer).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

# C0 (0x00-0x1F) and C1 (0x7F-0x9F) control characters, EXCEPT tab (\x09), newline (\x0a) and
# carriage return (\x0d), which are legitimate whitespace.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Code-execution / active-content sink patterns. Names are stable identifiers used in audit logs
# and span attributes. Matching is conservative (flag for human review), not a parser.
_SINK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python_eval_exec", re.compile(r"\b(?:eval|exec)\s*\(", re.IGNORECASE)),
    ("python_import", re.compile(r"__import__\s*\(", re.IGNORECASE)),
    (
        "unsafe_deserialize",
        re.compile(r"\b(?:pickle\.loads|yaml\.load|marshal\.loads)\s*\(", re.IGNORECASE),
    ),
    (
        "os_system",
        re.compile(r"\b(?:os\.system|subprocess\.(?:call|run|Popen))\s*\(", re.IGNORECASE),
    ),
    ("html_script", re.compile(r"<\s*script\b", re.IGNORECASE)),
    ("html_event_handler", re.compile(r"\bon[a-z]+\s*=\s*[\"']", re.IGNORECASE)),
    ("js_uri", re.compile(r"javascript:", re.IGNORECASE)),
    ("data_html_uri", re.compile(r"data:\s*text/html", re.IGNORECASE)),
    ("shell_substitution", re.compile(r"\$\([^)]*\)|`[^`]+`")),
    ("template_injection", re.compile(r"\{\{.+?\}\}|\$\{.+?\}")),
)


@dataclass
class SanitizationResult:
    """Result of sanitizing a single string."""

    text: str
    control_chars_stripped: int = 0
    markup_escaped: bool = False
    sinks_detected: list[str] = field(default_factory=list)

    @property
    def modified(self) -> bool:
        return self.control_chars_stripped > 0 or self.markup_escaped or bool(self.sinks_detected)


@dataclass
class OutputSanitationReport:
    """Aggregate report for sanitizing a structured value (dict/list/str)."""

    fields_examined: int = 0
    fields_escaped: int = 0
    control_chars_stripped: int = 0
    sinks_detected: list[str] = field(default_factory=list)

    @property
    def modified(self) -> bool:
        return (
            self.control_chars_stripped > 0 or self.fields_escaped > 0 or bool(self.sinks_detected)
        )


def strip_control_chars(text: str) -> tuple[str, int]:
    """Return ``(cleaned, count_removed)`` — control chars removed except tab/newline/CR."""
    cleaned = _CONTROL_CHARS.sub("", text)
    return cleaned, len(text) - len(cleaned)


def detect_code_exec_sinks(text: str) -> list[str]:
    """Return sorted, unique names of code-exec / active-content sinks present in ``text``."""
    return sorted({name for name, pattern in _SINK_PATTERNS if pattern.search(text)})


def escape_markup(text: str) -> str:
    """HTML-escape active markup for render contexts (operator UI, web logs)."""
    return html.escape(text, quote=True)


def sanitize_text(text: str, *, escape: bool = False) -> SanitizationResult:
    """Sanitize one LLM-output string.

    Always strips control characters and detects code-exec sinks. With ``escape=True`` (render
    contexts only) it also HTML-escapes markup — do NOT escape values that will be executed.
    """
    sinks = detect_code_exec_sinks(text)
    cleaned, stripped = strip_control_chars(text)
    escaped = False
    if escape:
        before = cleaned
        cleaned = escape_markup(cleaned)
        escaped = cleaned != before
    return SanitizationResult(
        text=cleaned, control_chars_stripped=stripped, markup_escaped=escaped, sinks_detected=sinks
    )


def sanitize_output(value: Any, *, escape: bool = False) -> tuple[Any, OutputSanitationReport]:
    """Recursively sanitize every string in an LLM-output structure (str / dict / list).

    Non-string leaves pass through untouched. Returns ``(sanitized_value, report)``. Use the default
    ``escape=False`` for values on the execution path; pass ``escape=True`` only for render output.
    """
    report = OutputSanitationReport()

    def _walk(node: Any) -> Any:
        if isinstance(node, str):
            result = sanitize_text(node, escape=escape)
            report.fields_examined += 1
            report.control_chars_stripped += result.control_chars_stripped
            if result.markup_escaped:
                report.fields_escaped += 1
            report.sinks_detected.extend(result.sinks_detected)
            return result.text
        if isinstance(node, dict):
            return {key: _walk(val) for key, val in node.items()}
        if isinstance(node, list):
            return [_walk(item) for item in node]
        return node

    sanitized = _walk(value)
    report.sinks_detected = sorted(set(report.sinks_detected))
    return sanitized, report
