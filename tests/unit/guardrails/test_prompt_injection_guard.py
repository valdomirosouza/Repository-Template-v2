"""Unit tests for src/guardrails/prompt_injection_guard.py.

Spec: specs/ai/guardrails.md (Layer 2 — Prompt Injection Guard)
ADR:  ADR-0010 (Agent Framework Selection)

All test inputs use clearly synthetic placeholder tokens.
No real exploit strings appear in this file.
"""

from src.guardrails.prompt_injection_guard import (
    PromptInjectionGuard,
    RejectionReason,
    ValidationResult,
)


class TestNormalInputs:
    def test_accepts_normal_question(self):
        guard = PromptInjectionGuard()
        result = guard.validate("What is the status of my order?")
        assert result.is_valid is True
        assert result.rejection_reason is None

    def test_accepts_multi_sentence_input(self):
        guard = PromptInjectionGuard()
        result = guard.validate("I need help with my account. The issue started yesterday.")
        assert result.is_valid is True

    def test_accepts_empty_string(self):
        guard = PromptInjectionGuard()
        result = guard.validate("")
        assert result.is_valid is True

    def test_accepts_short_input(self):
        guard = PromptInjectionGuard()
        result = guard.validate("Hello")
        assert result.is_valid is True

    def test_risk_score_low_for_normal_input(self):
        guard = PromptInjectionGuard()
        result = guard.validate("Please summarise the latest quarterly report.")
        assert result.risk_score < 0.7


class TestLengthValidation:
    def test_rejects_excessively_long_input(self):
        guard = PromptInjectionGuard(max_input_length=100)
        long_input = "a" * 200
        result = guard.validate(long_input)
        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.EXCESSIVE_LENGTH

    def test_accepts_input_at_exact_limit(self):
        guard = PromptInjectionGuard(max_input_length=100)
        result = guard.validate("a" * 100)
        assert result.is_valid is True

    def test_rejects_input_one_over_limit(self):
        guard = PromptInjectionGuard(max_input_length=100)
        result = guard.validate("a" * 101)
        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.EXCESSIVE_LENGTH


class TestStructuralAnomalyDetection:
    def test_high_repetition_rejected(self):
        guard = PromptInjectionGuard()
        # Synthetic placeholder — represents repetitive structural pattern
        repetitive = "SYNTHETIC_REPEAT_TOKEN " * 50
        result = guard.validate(repetitive)
        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.REPETITIVE_PATTERN

    def test_synthetic_role_override_risk_elevated(self):
        guard = PromptInjectionGuard()
        # Placeholder representing the structural shape of an override attempt
        synthetic = "SYNTHETIC_ROLE_OVERRIDE_PATTERN " * 20
        result = guard.validate(synthetic)
        assert result.risk_score > 0.5

    def test_normal_caps_word_not_flagged(self):
        guard = PromptInjectionGuard()
        result = guard.validate("The CEO approved the Q1 report.")
        assert result.is_valid is True


class TestEncodingValidation:
    def test_null_byte_stripped_in_sanitised_output(self):
        guard = PromptInjectionGuard()
        result = guard.validate("Hello\x00World")
        if result.is_valid:
            assert result.sanitised_input is not None
            assert "\x00" not in result.sanitised_input

    def test_many_null_bytes_rejected(self):
        guard = PromptInjectionGuard()
        result = guard.validate("\x00" * 100)
        assert result.is_valid is False


class TestSanitisation:
    def test_sanitised_input_returned_for_valid_input(self):
        guard = PromptInjectionGuard()
        result = guard.validate("Normal   text  with  spaces")
        if result.is_valid:
            assert result.sanitised_input is not None

    def test_risk_score_always_in_range(self):
        guard = PromptInjectionGuard()
        for text in ["", "hello", "a" * 1000, "SYNTHETIC_TOKEN " * 5]:
            result = guard.validate(text)
            assert 0.0 <= result.risk_score <= 1.0

    def test_result_never_raises(self):
        guard = PromptInjectionGuard()
        # validate() must never raise — always returns ValidationResult
        fraktur = "\U0001d573\U0001d58a\U0001d591\U0001d591\U0001d594"
        for text in [None.__class__.__name__, "\xff\xfe", fraktur]:
            result = guard.validate(text)
            assert isinstance(result, ValidationResult)
