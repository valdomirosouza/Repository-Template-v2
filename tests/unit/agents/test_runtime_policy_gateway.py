"""Unit tests for RuntimePolicyGateway — adaptive policy enforcement.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 3 (BM2)
ADR:  ADR-0049
Issue: #34
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.agents.runtime_policy_gateway import (
    Policy,
    PolicyCondition,
    PolicyDecision,
    RequestContext,
    RuntimePolicyError,
    RuntimePolicyGateway,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_policy(
    name: str,
    decision: PolicyDecision,
    task_type_pattern: str = "",
    proposed_action_type: str = "",
    method: tuple[str, ...] = (),
    pii_level_gte: str = "",
    reason: str = "",
) -> Policy:
    return Policy(
        name=name,
        condition=PolicyCondition(
            task_type_pattern=task_type_pattern,
            proposed_action_type=proposed_action_type,
            method=method,
            pii_level_gte=pii_level_gte,
        ),
        decision=decision,
        reason=reason,
    )


def _ctx(
    task_type: str = "",
    proposed_action_type: str = "",
    method: str = "",
    pii_level: str = "",
) -> RequestContext:
    return RequestContext(
        task_type=task_type,
        proposed_action_type=proposed_action_type,
        method=method,
        pii_level=pii_level,
    )


# ── Default ALLOW ─────────────────────────────────────────────────────────────


class TestDefaultAllow:
    def test_no_policies_returns_allow(self) -> None:
        gateway = RuntimePolicyGateway.from_list([])
        decision = gateway.evaluate("read_file", _ctx(task_type="summarise"))
        assert decision == PolicyDecision.ALLOW

    def test_no_matching_policy_returns_allow(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [_make_policy("block-write", PolicyDecision.BLOCK, proposed_action_type="write_file")]
        )
        decision = gateway.evaluate("read_file", _ctx(task_type="summarise"))
        assert decision == PolicyDecision.ALLOW


# ── task_type_pattern matching ────────────────────────────────────────────────


class TestTaskTypePattern:
    def test_exact_task_type_matches(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [_make_policy("p", PolicyDecision.BLOCK, task_type_pattern="summarise")]
        )
        assert gateway.evaluate("any_action", _ctx(task_type="summarise")) == PolicyDecision.BLOCK

    def test_wildcard_pattern_matches(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [_make_policy("p", PolicyDecision.BLOCK, task_type_pattern="summarise*")]
        )
        assert gateway.evaluate("any", _ctx(task_type="summarise-report")) == PolicyDecision.BLOCK

    def test_wildcard_does_not_match_different_prefix(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [_make_policy("p", PolicyDecision.BLOCK, task_type_pattern="summarise*")]
        )
        assert gateway.evaluate("any", _ctx(task_type="analyse-data")) == PolicyDecision.ALLOW


# ── proposed_action_type matching ─────────────────────────────────────────────


class TestActionTypeMatching:
    def test_exact_action_type_matches(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [_make_policy("p", PolicyDecision.REQUIRE_HITL, proposed_action_type="execute-code")]
        )
        decision = gateway.evaluate("execute-code", _ctx())
        assert decision == PolicyDecision.REQUIRE_HITL

    def test_different_action_type_does_not_match(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [_make_policy("p", PolicyDecision.BLOCK, proposed_action_type="execute-code")]
        )
        assert gateway.evaluate("read_file", _ctx()) == PolicyDecision.ALLOW


# ── method matching ───────────────────────────────────────────────────────────


class TestMethodMatching:
    def test_method_in_list_matches(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [
                _make_policy(
                    "p",
                    PolicyDecision.REQUIRE_HITL,
                    proposed_action_type="send-external-request",
                    method=("POST", "PUT"),
                )
            ]
        )
        assert (
            gateway.evaluate("send-external-request", _ctx(method="POST"))
            == PolicyDecision.REQUIRE_HITL
        )

    def test_method_not_in_list_does_not_match(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [
                _make_policy(
                    "p",
                    PolicyDecision.BLOCK,
                    proposed_action_type="send-external-request",
                    method=("POST",),
                )
            ]
        )
        assert gateway.evaluate("send-external-request", _ctx(method="GET")) == PolicyDecision.ALLOW


# ── PII level matching ────────────────────────────────────────────────────────


class TestPIILevelMatching:
    def test_l1_pii_matches_l2_gte_threshold(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [
                _make_policy(
                    "p",
                    PolicyDecision.REQUIRE_HITL,
                    proposed_action_type="write-db-record",
                    pii_level_gte="L2",
                )
            ]
        )
        # L1 is more sensitive than L2 → matches
        assert (
            gateway.evaluate("write-db-record", _ctx(pii_level="L1")) == PolicyDecision.REQUIRE_HITL
        )

    def test_l3_pii_does_not_match_l2_gte_threshold(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [
                _make_policy(
                    "p",
                    PolicyDecision.REQUIRE_HITL,
                    proposed_action_type="write-db-record",
                    pii_level_gte="L2",
                )
            ]
        )
        # L3 is less sensitive than L2 → does not match
        assert gateway.evaluate("write-db-record", _ctx(pii_level="L3")) == PolicyDecision.ALLOW


# ── First-match wins ──────────────────────────────────────────────────────────


class TestFirstMatchWins:
    def test_first_matching_policy_wins(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [
                _make_policy("p1", PolicyDecision.BLOCK, proposed_action_type="execute-code"),
                _make_policy("p2", PolicyDecision.ALLOW, proposed_action_type="execute-code"),
            ]
        )
        assert gateway.evaluate("execute-code", _ctx()) == PolicyDecision.BLOCK


# ── evaluate_or_raise ─────────────────────────────────────────────────────────


class TestEvaluateOrRaise:
    def test_block_raises_runtime_policy_error(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [
                _make_policy(
                    "p",
                    PolicyDecision.BLOCK,
                    proposed_action_type="execute-code",
                    reason="Not allowed here",
                )
            ]
        )
        with pytest.raises(RuntimePolicyError, match="BLOCKED"):
            gateway.evaluate_or_raise("execute-code", _ctx())

    def test_allow_does_not_raise(self) -> None:
        gateway = RuntimePolicyGateway.from_list([])
        result = gateway.evaluate_or_raise("read_file", _ctx())
        assert result == PolicyDecision.ALLOW

    def test_require_hitl_does_not_raise(self) -> None:
        gateway = RuntimePolicyGateway.from_list(
            [_make_policy("p", PolicyDecision.REQUIRE_HITL, proposed_action_type="write-db-record")]
        )
        result = gateway.evaluate_or_raise("write-db-record", _ctx())
        assert result == PolicyDecision.REQUIRE_HITL


# ── from_yaml ─────────────────────────────────────────────────────────────────


class TestFromYaml:
    def test_loads_policies_from_yaml(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            policies:
              - name: block-code-on-summarize
                condition:
                  task_type_pattern: "summarise*"
                  proposed_action_type: "execute-code"
                decision: BLOCK
                reason: "Code not allowed for summarize tasks"
              - name: hitl-external-writes
                condition:
                  proposed_action_type: "send-external-request"
                  method: ["POST"]
                decision: REQUIRE_HITL
                reason: "External writes require HITL"
        """)
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(yaml_content)
        gateway = RuntimePolicyGateway.from_yaml(policy_file)
        assert gateway.policy_count == 2
        assert (
            gateway.evaluate("execute-code", _ctx(task_type="summarise-report"))
            == PolicyDecision.BLOCK
        )

    def test_empty_yaml_gives_empty_gateway(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text("{}")
        gateway = RuntimePolicyGateway.from_yaml(policy_file)
        assert gateway.policy_count == 0


# ── hot reload ────────────────────────────────────────────────────────────────


class TestHotReload:
    def test_reload_updates_policies(self, tmp_path: Path) -> None:
        initial = textwrap.dedent("""\
            policies:
              - name: block-write
                condition:
                  proposed_action_type: "write_file"
                decision: BLOCK
                reason: "Initial"
        """)
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(initial)
        gateway = RuntimePolicyGateway.from_yaml(policy_file)
        assert gateway.evaluate("write_file", _ctx()) == PolicyDecision.BLOCK

        # Hot-reload with no policies
        policy_file.write_text("policies: []")
        gateway.reload(policy_file)
        assert gateway.evaluate("write_file", _ctx()) == PolicyDecision.ALLOW
        assert gateway.policy_count == 0
