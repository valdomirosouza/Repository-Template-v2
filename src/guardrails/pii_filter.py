"""PII detection and masking with L1-L4 classification.

Detection uses structural format patterns only — no real personal data is stored
in this module. Masking tokens replace matched values; originals are never logged
or forwarded.

Spec: specs/ai/guardrails.md (Layer 1 — PII Filter)
ADR:  ADR-0012 (PII Masking Strategy)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar


class PIILevel(Enum):
    L1_CRITICAL = 1  # CPF/SSN, health data, biometric — never in logs or LLM
    L2_SENSITIVE = 2  # name, email, phone, IP — mask in logs
    L3_INTERNAL = 3  # session token, UUID — internal audit only
    L4_PUBLIC = 4  # declared role, org name — no special handling


@dataclass
class PIIMatch:
    field_type: str  # e.g. "EMAIL", "CPF", "IP"
    level: PIILevel
    start: int
    end: int
    replacement_token: str  # e.g. "[EMAIL]"


class PIIFilter:
    """Detects and replaces PII patterns in text and dictionaries.

    Uses structural format patterns only. No real personal data is stored here.
    On match, the original value is replaced with a token and discarded.
    """

    # Compiled once at import time — patterns are stateless and shared across all instances.
    _PATTERNS: ClassVar[list[tuple[str, PIILevel, re.Pattern[str], str]]] = [
        # L1 — Critical
        (
            "CPF",
            PIILevel.L1_CRITICAL,
            re.compile(r"\b\d{3}[.\-]?\d{3}[.\-]?\d{3}[.\-]?\d{2}\b"),
            "[CPF]",
        ),
        (
            "CARD",
            PIILevel.L1_CRITICAL,
            # Structural: 13-19 digit groups separated by spaces or dashes
            re.compile(r"\b(?:\d[ \-]?){13,19}\d\b"),
            "[CARD]",
        ),
        # L2 — Sensitive
        (
            "EMAIL",
            PIILevel.L2_SENSITIVE,
            re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
            "[EMAIL]",
        ),
        (
            "PHONE",
            PIILevel.L2_SENSITIVE,
            re.compile(r"(?:\+\d{1,3}[\s\-]?)?(?:\(?\d{2,3}\)?[\s\-]?)?\d{4,5}[\s\-]?\d{4}\b"),
            "[PHONE]",
        ),
        (
            "IP",
            PIILevel.L2_SENSITIVE,
            re.compile(
                r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
                r"|(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
            ),
            "[IP]",
        ),
        # L2 — Sensitive (continued)
        (
            "TOKEN",
            PIILevel.L2_SENSITIVE,
            # JWT structural shape: three base64url segments separated by dots
            re.compile(r"\b[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
            "[TOKEN]",
        ),
        (
            "UUID",
            PIILevel.L3_INTERNAL,
            re.compile(
                r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
            ),
            "[UUID]",
        ),
    ]

    def detect(self, text: str) -> list[PIIMatch]:
        """Return all PII matches found, without masking."""
        matches: list[PIIMatch] = []
        for field_type, level, pattern, token in self._PATTERNS:
            for m in pattern.finditer(text):
                matches.append(
                    PIIMatch(
                        field_type=field_type,
                        level=level,
                        start=m.start(),
                        end=m.end(),
                        replacement_token=token,
                    )
                )
        return sorted(matches, key=lambda x: x.start)

    def mask_text(self, text: str, min_level: PIILevel = PIILevel.L2_SENSITIVE) -> str:
        """Replace all PII at or above min_level with replacement tokens.

        All detected patterns (including those above min_level) claim their regions
        first to prevent lower-priority patterns from matching within them.  For
        example, a UUID (L3) at L2 threshold is not replaced but still blocks CARD
        and PHONE patterns from matching its digit groups.
        The original matched value is never stored after replacement.
        """
        result = text
        offset = 0
        all_matches = self.detect(text)
        # Longest span first; for equal spans prefer higher-priority (lower level value)
        all_matches.sort(key=lambda m: (m.start, -(m.end - m.start), m.level.value))
        last_end = 0
        for match in all_matches:
            if match.start < last_end:
                continue  # skip overlapping regardless of level
            last_end = match.end  # claim region even if not replacing
            if match.level.value > min_level.value:
                continue  # above threshold — region blocked but not masked
            start = match.start + offset
            end = match.end + offset
            result = result[:start] + match.replacement_token + result[end:]
            offset += len(match.replacement_token) - (match.end - match.start)
        return result

    def mask_dict(
        self,
        data: dict[str, Any],
        min_level: PIILevel = PIILevel.L2_SENSITIVE,
    ) -> dict[str, Any]:
        """Recursively mask PII in all string values of a dictionary."""
        return self._mask_value(data, min_level)  # type: ignore[no-any-return]

    def _mask_value(self, value: Any, min_level: PIILevel) -> Any:
        if isinstance(value, str):
            return self.mask_text(value, min_level)
        if isinstance(value, dict):
            return {k: self._mask_value(v, min_level) for k, v in value.items()}
        if isinstance(value, list):
            return [self._mask_value(item, min_level) for item in value]
        return value


# Module-level singleton and convenience functions
pii_filter = PIIFilter()


def mask_text(
    text: str,
    min_level: PIILevel = PIILevel.L2_SENSITIVE,
) -> str:
    return pii_filter.mask_text(text, min_level)


def mask_dict(
    data: dict[str, Any],
    min_level: PIILevel = PIILevel.L2_SENSITIVE,
) -> dict[str, Any]:
    return pii_filter.mask_dict(data, min_level)
