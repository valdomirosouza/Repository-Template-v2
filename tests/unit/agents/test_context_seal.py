"""Unit tests for ContextSeal — harness stage integrity.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 1 (SD2)
ADR:  ADR-0047
Issue: #32
"""

from __future__ import annotations

import hashlib
import json

import pytest

from src.agents.harness.context_seal import ContextSeal, ContextTamperingError, SealedContext


class TestContextSealSign:
    def test_sign_returns_sealed_context(self) -> None:
        ctx = {"task_id": "t-1", "description": "Do something"}
        sealed = ContextSeal.sign(ctx)
        assert isinstance(sealed, SealedContext)
        assert sealed.context == ctx

    def test_sign_computes_correct_sha256(self) -> None:
        ctx = {"key": "value"}
        sealed = ContextSeal.sign(ctx)
        expected = hashlib.sha256(
            json.dumps(ctx, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        assert sealed.sha256 == expected

    def test_sign_includes_signed_at_timestamp(self) -> None:
        sealed = ContextSeal.sign({"x": 1})
        assert sealed.signed_at  # non-empty ISO-8601 string
        assert "T" in sealed.signed_at  # rough ISO format check

    def test_two_identical_contexts_produce_same_sha256(self) -> None:
        ctx = {"a": 1, "b": [2, 3]}
        assert ContextSeal.sign(ctx).sha256 == ContextSeal.sign(ctx).sha256

    def test_different_contexts_produce_different_sha256(self) -> None:
        assert ContextSeal.sign({"a": 1}).sha256 != ContextSeal.sign({"a": 2}).sha256

    def test_sign_is_key_order_independent(self) -> None:
        ctx_a = {"b": 2, "a": 1}
        ctx_b = {"a": 1, "b": 2}
        # sort_keys=True makes order irrelevant
        assert ContextSeal.sign(ctx_a).sha256 == ContextSeal.sign(ctx_b).sha256


class TestContextSealVerify:
    def test_verify_returns_original_context(self) -> None:
        ctx = {"task_id": "t-2", "sprint_count": 3}
        sealed = ContextSeal.sign(ctx)
        result = ContextSeal.verify(sealed)
        assert result == ctx

    def test_verify_raises_on_sha256_mismatch(self) -> None:
        ctx = {"data": "original"}
        sealed = ContextSeal.sign(ctx)
        # Tamper: replace sha256 with wrong value
        tampered = SealedContext(
            context=sealed.context,
            sha256="0" * 64,
            signed_at=sealed.signed_at,
        )
        with pytest.raises(ContextTamperingError, match="Context integrity seal FAILED"):
            ContextSeal.verify(tampered)

    def test_verify_raises_when_context_mutated(self) -> None:
        ctx = {"data": "original"}
        sealed = ContextSeal.sign(ctx)
        # Tamper: mutate the context dict but keep the original sha256
        mutated_ctx = {"data": "injected malicious instruction"}
        tampered = SealedContext(
            context=mutated_ctx,
            sha256=sealed.sha256,  # original hash no longer matches
            signed_at=sealed.signed_at,
        )
        with pytest.raises(ContextTamperingError):
            ContextSeal.verify(tampered)

    def test_verify_passes_for_untampered_seal(self) -> None:
        ctx = {"sprint_contracts": [{"id": "s1", "objectives": ["obj1"]}]}
        sealed = ContextSeal.sign(ctx)
        result = ContextSeal.verify(sealed)
        assert result["sprint_contracts"][0]["id"] == "s1"

    def test_empty_dict_round_trips(self) -> None:
        sealed = ContextSeal.sign({})
        result = ContextSeal.verify(sealed)
        assert result == {}

    def test_nested_dict_round_trips(self) -> None:
        ctx = {"level1": {"level2": {"level3": [1, 2, 3]}}}
        sealed = ContextSeal.sign(ctx)
        assert ContextSeal.verify(sealed) == ctx
