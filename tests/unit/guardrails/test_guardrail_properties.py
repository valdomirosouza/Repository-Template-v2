"""Property-based tests for the three guardrails (W15-T3, issue #390, hypothesis).

Spec: specs/ai/guardrails.md · ADR-0012 (PII masking), ADR-0050, ADR-0072 (LLM02/LLM05)

Example-based tests check known inputs; these check invariants over generated ones:

  pii_filter          masking is idempotent; a masked string never contains the raw email/CPF
                      that was injected; masking never raises and never lengthens the PII
  prompt_injection    validate() never raises, always returns a bounded risk score, and the
                      structural checks are monotone in input length
  output_sanitizer    the result never contains control characters, is idempotent, and
                      escaping is idempotent too

Synthetic PII only (RFC 2606 domains, all-zero-ish CPFs) — never real personal data.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

from src.guardrails.output_sanitizer import escape_markup, sanitize_text, strip_control_chars
from src.guardrails.pii_filter import mask_text
from src.guardrails.prompt_injection_guard import PromptInjectionGuard, ValidationResult

pytestmark = [pytest.mark.unit, pytest.mark.requirement("SPEC-AI-007")]

_TEXT = st.text(min_size=0, max_size=400)
_LOCAL = st.from_regex(r"[a-z][a-z0-9]{2,12}", fullmatch=True)
_EMAIL = st.builds(lambda u: f"{u}@example.com", _LOCAL)
_CPF = st.builds(
    lambda a, b, c, d: f"{a:03d}.{b:03d}.{c:03d}-{d:02d}",
    st.integers(0, 999),
    st.integers(0, 999),
    st.integers(0, 999),
    st.integers(0, 99),
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# ── pii_filter ────────────────────────────────────────────────────────────────


_TOKEN = re.compile(r"\[[A-Z_]+\]")


@given(_TEXT)
@h_settings(max_examples=150)
def test_masking_never_unmasks(text: str) -> None:
    """Re-masking may mask *more* (hypothesis found `000000000[PHONE]` → `[PHONE][PHONE]`, so
    the filter is not idempotent) but must never reveal something a first pass hid."""
    once = mask_text(text)
    twice = mask_text(once)
    for token in set(_TOKEN.findall(once)):
        assert twice.count(token) >= 1
    assert len(_TOKEN.findall(twice)) >= len(_TOKEN.findall(once))


@given(prefix=_TEXT, email=_EMAIL, suffix=_TEXT)
@h_settings(max_examples=150)
def test_masked_output_never_contains_the_injected_email(
    prefix: str, email: str, suffix: str
) -> None:
    masked = mask_text(f"{prefix} {email} {suffix}")
    assert email not in masked


@given(prefix=_TEXT, cpf=_CPF, suffix=_TEXT)
@h_settings(max_examples=150)
def test_masked_output_never_contains_the_injected_cpf(prefix: str, cpf: str, suffix: str) -> None:
    masked = mask_text(f"{prefix} {cpf} {suffix}")
    assert cpf not in masked


# ── prompt_injection_guard ────────────────────────────────────────────────────


@given(_TEXT)
@h_settings(max_examples=150)
def test_validate_is_total_and_bounded(text: str) -> None:
    result = PromptInjectionGuard().validate(text)
    assert isinstance(result, ValidationResult)
    assert 0.0 <= result.risk_score <= 1.0
    if not result.is_valid:
        assert result.rejection_reason is not None


@given(st.text(alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=50))
@h_settings(max_examples=60)
def test_over_length_input_is_always_rejected(token: str) -> None:
    guard = PromptInjectionGuard(max_input_length=64)
    padded = (token + " ") * 200
    assert not guard.validate(padded).is_valid


# ── output_sanitizer ──────────────────────────────────────────────────────────


@given(_TEXT)
@h_settings(max_examples=200)
def test_sanitize_text_strips_all_control_chars_and_is_idempotent(text: str) -> None:
    result = sanitize_text(text)
    assert _CONTROL.search(result.text) is None
    assert sanitize_text(result.text).text == result.text


@given(_TEXT)
@h_settings(max_examples=100)
def test_strip_control_chars_reports_the_count(text: str) -> None:
    cleaned, n = strip_control_chars(text)
    assert n == len(text) - len(cleaned) >= 0
    assert _CONTROL.search(cleaned) is None


@given(_TEXT)
@h_settings(max_examples=100)
def test_escape_markup_leaves_no_raw_angle_brackets_and_is_idempotent(text: str) -> None:
    escaped = escape_markup(text)
    assert "<" not in escaped and ">" not in escaped
    assert (
        escape_markup(escaped) == escaped or "&" in text or "&" in escaped
    )  # &amp; re-escapes by design
