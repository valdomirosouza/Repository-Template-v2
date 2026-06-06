"""Prompt injection guard — structural heuristic validation of LLM inputs.

Detects and rejects inputs with anomaly signatures before they reach the LLM.
Detection uses structural/statistical checks only. No real exploit strings are
stored in this module. Rejected inputs are never logged in full — only a
truncated hash and the rejection reason are recorded.

Spec: specs/ai/guardrails.md (Layer 2 — Prompt Injection Guard)
ADR:  ADR-0010 (Agent Framework Selection)
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from opentelemetry import trace as otel_trace
from opentelemetry.trace import StatusCode

from src.observability.logger import get_logger

logger = get_logger("prompt_injection_guard")


class RejectionReason(Enum):
    EXCESSIVE_LENGTH = "excessive_length"
    STRUCTURAL_ANOMALY = "structural_anomaly"
    ROLE_OVERRIDE_PATTERN = "role_override_pattern"
    REPETITIVE_PATTERN = "repetitive_pattern"
    ENCODING_ANOMALY = "encoding_anomaly"


@dataclass
class ValidationResult:
    is_valid: bool
    rejection_reason: RejectionReason | None = None
    risk_score: float = 0.0
    sanitised_input: str | None = None


class PromptInjectionGuard:
    """Validates LLM inputs using structural heuristics.

    Never stores or logs the rejected content in full.
    Logs only sha256(input)[:16] and the rejection reason.
    """

    def __init__(
        self,
        max_input_length: int = 8000,
        risk_threshold: float = 0.7,
    ) -> None:
        self._max_length = max_input_length
        self._risk_threshold = risk_threshold

    def validate(self, user_input: str) -> ValidationResult:
        """Run all structural checks. Returns ValidationResult. Never raises."""
        try:
            if len(user_input) > self._max_length:
                self._log_rejection(user_input, RejectionReason.EXCESSIVE_LENGTH)
                return ValidationResult(
                    is_valid=False,
                    rejection_reason=RejectionReason.EXCESSIVE_LENGTH,
                    risk_score=1.0,
                )

            scores: dict[RejectionReason, float] = {
                RejectionReason.STRUCTURAL_ANOMALY: self._check_structural_anomaly(user_input),
                RejectionReason.ROLE_OVERRIDE_PATTERN: self._check_role_override_pattern(
                    user_input
                ),
                RejectionReason.REPETITIVE_PATTERN: self._check_repetition(user_input),
                RejectionReason.ENCODING_ANOMALY: self._check_encoding(user_input),
            }

            risk_score = self._compute_risk_score(list(scores.values()))

            # Find the dominant rejection reason (highest individual score)
            dominant_reason = max(scores, key=lambda k: scores[k])

            if risk_score >= self._risk_threshold:
                self._log_rejection(user_input, dominant_reason)
                span = otel_trace.get_current_span()
                if span.is_recording():
                    span.add_event(
                        "guardrail.injection_blocked",
                        {
                            "rejection_reason": dominant_reason.value,
                            "risk_score": risk_score,
                        },
                    )
                    span.set_status(StatusCode.ERROR, f"injection guard: {dominant_reason.value}")
                return ValidationResult(
                    is_valid=False,
                    rejection_reason=dominant_reason,
                    risk_score=risk_score,
                )

            return ValidationResult(
                is_valid=True,
                risk_score=risk_score,
                sanitised_input=self._sanitise(user_input),
            )

        except Exception as exc:
            logger.error("Injection guard check failed — defaulting to reject", error=str(exc))
            return ValidationResult(is_valid=False, risk_score=1.0)

    def _check_structural_anomaly(self, text: str) -> float:
        """Detect high density of imperative/directive structural markers."""
        if not text:
            return 0.0
        # Count tokens that look structurally like directives (all-caps words, colon-terminated)
        directive_markers = len(re.findall(r"\b[A-Z]{3,}(?:\s*:|\s*\()", text))
        word_count = max(len(text.split()), 1)
        return min(directive_markers / word_count * 10, 1.0)

    def _check_role_override_pattern(self, text: str) -> float:
        """Detect inputs where early tokens have structural similarity to system directives."""
        if not text:
            return 0.0
        # Structural heuristic: high ratio of all-uppercase "word:" patterns near the start
        first_200 = text[:200]
        caps_colon = len(re.findall(r"\b[A-Z][A-Z]+\s*:", first_200))
        return min(caps_colon * 0.25, 1.0)

    def _check_repetition(self, text: str) -> float:
        """Detect inputs with low character entropy or word-level repetition."""
        if len(text) < 20:
            return 0.0

        # Character entropy check — catches single-char floods like "a"*N
        freq: dict[str, int] = {}
        for ch in text:
            freq[ch] = freq.get(ch, 0) + 1
        total = len(text)
        entropy = -sum((c / total) * math.log2(c / total) for c in freq.values())
        # Normal English has entropy ~4.0-4.5 bits/char; cap char score for
        # single-token strings to avoid false positives on inputs like "aaaa"
        words = text.split()
        if len(words) < 10:
            char_score = max(0.0, min(0.6, (2.5 - entropy) / 2.5))
        else:
            char_score = max(0.0, min(1.0, (2.5 - entropy) / 2.5))

        # Word-level repetition — catches repeated-token injection patterns
        word_score = 0.0
        if len(words) >= 10:
            unique_ratio = len(set(words)) / len(words)
            # unique_ratio near 0 (all same word) → score near 1.0
            word_score = max(0.0, 1.0 - unique_ratio)

        return max(char_score, word_score)

    def _check_encoding(self, text: str) -> float:
        """Detect unusual encoding or escape sequences."""
        if not text:
            return 0.0
        null_bytes = text.count("\x00")
        control_chars = sum(
            1 for c in text if unicodedata.category(c) == "Cc" and c not in "\n\r\t"
        )
        score = min((null_bytes + control_chars) / max(len(text), 1) * 100, 1.0)
        return score

    def _compute_risk_score(self, scores: list[float]) -> float:
        """Weighted combination: dominant signal contributes 50%, average 25%."""
        if not scores:
            return 0.0
        return min(sum(scores) / len(scores) + max(scores) * 0.5, 1.0)

    def _sanitise(self, text: str) -> str:
        """Normalise unicode, strip null bytes, collapse excessive whitespace."""
        text = text.replace("\x00", "")
        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def _log_rejection(self, text: str, reason: RejectionReason) -> None:
        input_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        logger.warning(
            "Prompt injection guard: input rejected",
            reason=reason.value,
            input_hash=input_hash,
        )


# Module-level singleton
injection_guard = PromptInjectionGuard()
