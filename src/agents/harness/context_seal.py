"""Context integrity seal for harness stage boundaries.

Prevents a compromised or hallucinating Planner from injecting instructions into
the Generator's context without detection. The Planner signs its output; the
Generator verifies the seal before consuming.

Any mismatch triggers ContextTamperingError which the coordinator escalates to HITL.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 1 (SD2)
ADR:  ADR-0047
Issue: #32
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class ContextTamperingError(Exception):
    """Raised when a harness context seal fails verification — indicates tampering or corruption."""


@dataclass(frozen=True)
class SealedContext:
    """A context dict bundled with its SHA-256 integrity seal."""

    context: dict[str, Any]
    sha256: str
    signed_at: str  # ISO-8601 UTC timestamp


class ContextSeal:
    """Sign and verify context dicts passed between harness stages.

    Usage (Planner → Generator boundary)::

        sealed = ContextSeal.sign(spec.to_dict())
        # pass `sealed` to Generator
        context = ContextSeal.verify(sealed)  # raises ContextTamperingError on mismatch
    """

    @staticmethod
    def sign(context: dict[str, Any]) -> SealedContext:
        """Compute a SHA-256 digest of the serialized context and return a sealed bundle."""
        serialized = json.dumps(context, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return SealedContext(
            context=context,
            sha256=digest,
            signed_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def verify(sealed: SealedContext) -> dict[str, Any]:
        """Verify the seal and return the original context dict.

        Raises:
            ContextTamperingError: if the recomputed SHA-256 does not match the stored digest.
        """
        serialized = json.dumps(sealed.context, sort_keys=True, ensure_ascii=True)
        expected = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        if expected != sealed.sha256:
            raise ContextTamperingError(
                f"Context integrity seal FAILED. "
                f"Expected SHA-256={expected!r}, got {sealed.sha256!r}. "
                "Possible tampering or in-memory corruption between harness stages. "
                "Escalating to HITL."
            )
        return sealed.context
