"""Unit tests for src/agents/orchestrator/orchestrator.py.

Spec: specs/ai/agent-design.md
ADR:  ADR-0010 (Agent Framework Selection), ADR-0011 (HITL/HOTL Model),
      ADR-0048 (zero-trust tool registry), ADR-0053 (runtime enforcement)

All test inputs use clearly synthetic, obviously fake data.
No real personal data appears in this file.

P0-4 contract: every action the orchestrator executes must route through the
governed ToolExecutor. Only *registered* tools execute; at the safest default
autonomy level (NONE) every action falls back to HITL. Tests therefore use the
registered starter-catalog tool names (read-db-record, write-db-record, …) and
configure OpenFeature autonomy flags explicitly when autonomous execution is
under test.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from openfeature import api
from openfeature.provider.in_memory_provider import InMemoryFlag, InMemoryProvider

from src.agents.compensation_registry import CompensationRegistry
from src.agents.hitl_gateway import HITLStatus
from src.agents.hotl_monitor import HOTLMonitor
from src.agents.orchestrator.orchestrator import AgentOrchestrator
from src.agents.override_service import OverrideService
from src.agents.tool_executor import ToolExecutor, ToolNotRegisteredError
from src.agents.tool_registry import ToolDefinition, ToolRegistry, ToolRiskLevel
from src.guardrails.audit_logger import AuditWriteError
from src.shared.llm_client import StubLLMClient

# ── OpenFeature provider helpers (autonomy levels are global flag state) ───────


def _make_bool_flag(enabled: bool) -> InMemoryFlag:
    variant = "on" if enabled else "off"
    return InMemoryFlag(default_variant=variant, variants={"on": True, "off": False})


def _set_provider(**flags: bool) -> None:
    in_memory_flags = {name: _make_bool_flag(val) for name, val in flags.items()}
    api.set_provider(InMemoryProvider(in_memory_flags))


def _all_off() -> None:
    """Safest-default autonomy: NONE — every action requires HITL."""
    _set_provider(
        **{
            "autonomous-mode": False,
            "autonomous-mode-full": False,
            "autonomous-mode-medium-risk": False,
            "autonomous-mode-low-risk": False,
            "autonomous-mode-tests-only": False,
            "autonomous-mode-read-only": False,
        }
    )


@pytest.fixture(autouse=True)
def _reset_autonomy_to_none() -> None:
    """Reset OpenFeature to all-flags-off before every test (NONE autonomy).

    Other test modules mutate the global provider; pin it here for determinism.
    """
    _all_off()


def _make_audit(side_effect=None) -> MagicMock:
    audit = MagicMock()
    audit.log_event = AsyncMock(side_effect=side_effect)
    return audit


def _make_gateway(status: HITLStatus = HITLStatus.APPROVED) -> MagicMock:
    gateway = MagicMock()
    approved = MagicMock()
    approved.status = status
    gateway.submit_for_approval = AsyncMock(return_value=approved)
    return gateway


def _make_orchestrator(
    llm_response: str | None = None,
    gateway_status: HITLStatus = HITLStatus.APPROVED,
    audit: MagicMock | None = None,
) -> AgentOrchestrator:
    if llm_response is None:
        # read-db-record is a registered, low-risk, no-HITL starter-catalog tool.
        llm_response = json.dumps({"action": "read-db-record", "parameters": {}, "risk_score": 0.1})
    return AgentOrchestrator(
        agent_id="test-orchestrator",
        audit_logger=audit or _make_audit(),
        hitl_gateway=_make_gateway(gateway_status),
        llm_client=StubLLMClient(llm_response),
    )


class TestPerceive:
    @pytest.mark.asyncio
    async def test_pii_masked_in_result(self) -> None:
        # Synthetic email — must not appear raw in the returned result dict
        orchestrator = _make_orchestrator()

        result = await orchestrator.run(
            raw_input={"request_text": "Contact fake@example.com for details"},
        )

        assert "fake@example.com" not in str(result)

    @pytest.mark.asyncio
    async def test_injection_attempt_raises_value_error(self) -> None:
        # Synthetic injection: REPETITIVE_PATTERN trigger (80x repetition)
        orchestrator = _make_orchestrator()
        malicious = "SYNTHETIC_INJECT_ATTEMPT " * 80

        with pytest.raises(ValueError, match="rejected"):
            await orchestrator.run(raw_input={"request_text": malicious})


class TestReason:
    @pytest.mark.asyncio
    async def test_valid_json_populates_action_and_risk(self) -> None:
        # RiskScorer overrides the LLM-provided risk_score (0.2) with its own
        # computed score. "read-db-record" → 0.1 irreversibility (read action)
        # → 0.35×0.1 + 0.25×0.2 + 0.20×0.1 = 0.105.
        llm_json = json.dumps(
            {
                "action": "read-db-record",
                "parameters": {"record_id": "synthetic-123"},
                "risk_score": 0.2,
            }
        )
        orchestrator = _make_orchestrator(llm_response=llm_json)

        result = await orchestrator.run(raw_input={"request_text": "Fetch a record"})

        assert result["action"] == "read-db-record"
        assert result["risk_score"] == pytest.approx(0.105)

    @pytest.mark.asyncio
    async def test_invalid_llm_json_blocks_unregistered_action(self) -> None:
        # Unparseable LLM output → action="unknown" → NOT a registered tool.
        # Zero-trust: unregistered actions are blocked at execution (fail-closed).
        orchestrator = _make_orchestrator(llm_response="not valid json {{{{")

        with pytest.raises(ToolNotRegisteredError):
            await orchestrator.run(raw_input={"request_text": "Do something"})

    @pytest.mark.asyncio
    async def test_schema_invalid_output_routes_to_hitl(self) -> None:
        # A registered tool with a malformed agent_action_v1 envelope (bad enum)
        # must route to HITL — never silently proceed (ADR-0054).
        llm_json = json.dumps(
            {
                "schema_version": "agent_action_v1",
                "action_type": "read-db-record",
                "parameters": {},
                "operation": "obliterate",  # invalid enum
            }
        )
        gateway = _make_gateway(HITLStatus.APPROVED)
        orchestrator = AgentOrchestrator(
            agent_id="test-agent",
            audit_logger=_make_audit(),
            hitl_gateway=gateway,
            llm_client=StubLLMClient(llm_json),
        )

        result = await orchestrator.run(raw_input={"request_text": "Read a record"})

        gateway.submit_for_approval.assert_called_once()
        assert result["oversight_mode"] == "HITL_SCHEMA_INVALID"
        assert result["outcome"] == "EXECUTED"

    @pytest.mark.asyncio
    async def test_missing_risk_score_uses_risk_scorer(self) -> None:
        # LLM omits risk_score — RiskScorer computes based on action+parameters.
        # "read-db-record" with empty params → 0.105 (read action).
        llm_json = json.dumps({"action": "read-db-record", "parameters": {}})
        orchestrator = _make_orchestrator(llm_response=llm_json)

        result = await orchestrator.run(raw_input={"request_text": "Run read"})

        assert result["risk_score"] == pytest.approx(0.105)

    @pytest.mark.asyncio
    async def test_parameters_passed_through_to_result(self) -> None:
        llm_json = json.dumps(
            {"action": "read-db-record", "parameters": {"depth": "full"}, "risk_score": 0.1}
        )
        orchestrator = _make_orchestrator(llm_response=llm_json)

        result = await orchestrator.run(raw_input={"request_text": "Read data"})

        assert result["parameters"] == {"depth": "full"}


class TestAct:
    @pytest.mark.asyncio
    async def test_low_risk_executes_without_hitl(self) -> None:
        # LOW_RISK autonomy enabled → low-risk registered tool executes autonomously.
        _set_provider(**{"autonomous-mode-low-risk": True})
        llm_json = json.dumps({"action": "read-db-record", "parameters": {}, "risk_score": 0.1})
        gateway = _make_gateway()
        orchestrator = AgentOrchestrator(
            agent_id="test-agent",
            audit_logger=_make_audit(),
            hitl_gateway=gateway,
            llm_client=StubLLMClient(llm_json),
        )

        result = await orchestrator.run(raw_input={"request_text": "Show me the record"})

        assert result["outcome"] == "EXECUTED"
        assert result["oversight_mode"] == "HOTL_LOW_RISK"
        gateway.submit_for_approval.assert_not_called()

    @pytest.mark.asyncio
    async def test_high_risk_routes_to_hitl(self) -> None:
        # write-db-record is a mandatory-HITL registered tool — always routes to HITL.
        llm_json = json.dumps({"action": "write-db-record", "parameters": {}, "risk_score": 0.9})
        gateway = _make_gateway(HITLStatus.APPROVED)
        orchestrator = AgentOrchestrator(
            agent_id="test-agent",
            audit_logger=_make_audit(),
            hitl_gateway=gateway,
            llm_client=StubLLMClient(llm_json),
        )

        result = await orchestrator.run(raw_input={"request_text": "Persist this record"})

        gateway.submit_for_approval.assert_called_once()
        assert result["outcome"] == "EXECUTED"

    @pytest.mark.asyncio
    async def test_hitl_rejection_raises_value_error(self) -> None:
        llm_json = json.dumps({"action": "write-db-record", "parameters": {}, "risk_score": 0.9})
        orchestrator = _make_orchestrator(
            llm_response=llm_json,
            gateway_status=HITLStatus.REJECTED,
        )

        with pytest.raises(ValueError, match="rejected"):
            await orchestrator.run(raw_input={"request_text": "Persist this record"})

    @pytest.mark.asyncio
    async def test_pending_status_suspends_action(self) -> None:
        # P0-1: a PENDING HITL response is a valid suspension state, not a failure.
        llm_json = json.dumps({"action": "write-db-record", "parameters": {}, "risk_score": 0.9})
        orchestrator = _make_orchestrator(
            llm_response=llm_json,
            gateway_status=HITLStatus.PENDING,
        )

        result = await orchestrator.run(raw_input={"request_text": "Persist this record"})

        assert result["status"] == "waiting_for_human_approval"
        assert result["outcome"] == "PENDING"
        assert "hitl_request_id" in result

    @pytest.mark.asyncio
    async def test_audit_write_error_blocks_action(self) -> None:
        llm_json = json.dumps({"action": "read-db-record", "parameters": {}, "risk_score": 0.1})
        audit = _make_audit(side_effect=AuditWriteError("disk full"))
        orchestrator = _make_orchestrator(llm_response=llm_json, audit=audit)

        with pytest.raises(AuditWriteError):
            await orchestrator.run(raw_input={"request_text": "Read logs"})

    @pytest.mark.asyncio
    async def test_pending_audit_written_before_executed(self) -> None:
        # Write-before-execute invariant: first audit is PENDING (proposed),
        # last audit is EXECUTED (post-execution from ToolExecutor).
        llm_json = json.dumps({"action": "read-db-record", "parameters": {}, "risk_score": 0.1})
        audit = _make_audit()
        orchestrator = _make_orchestrator(llm_response=llm_json, audit=audit)

        await orchestrator.run(raw_input={"request_text": "Read logs"})

        outcomes = [c[0][0].outcome for c in audit.log_event.call_args_list]
        assert outcomes[0] == "PENDING"
        assert outcomes[-1] == "EXECUTED"
        assert "EXECUTING" in outcomes

    @pytest.mark.asyncio
    async def test_result_contains_expected_fields(self) -> None:
        llm_json = json.dumps(
            {"action": "read-db-record", "parameters": {"depth": "full"}, "risk_score": 0.2}
        )
        orchestrator = _make_orchestrator(llm_response=llm_json)

        result = await orchestrator.run(
            raw_input={"request_text": "Read data"},
            trace_id="trace-unit-xyz",
        )

        assert result["agent_id"] == "test-orchestrator"
        assert result["action"] == "read-db-record"
        assert result["parameters"] == {"depth": "full"}
        assert result["outcome"] == "EXECUTED"
        assert result["trace_id"] == "trace-unit-xyz"

    @pytest.mark.asyncio
    async def test_trace_id_propagated_to_result(self) -> None:
        orchestrator = _make_orchestrator()

        result = await orchestrator.run(
            raw_input={"request_text": "Any task"},
            trace_id="trace-propagation-test",
        )

        assert result["trace_id"] == "trace-propagation-test"


class TestHOTLLifecycle:
    """ADR-0055 — reversibility gate + HOTL monitor integration."""

    @pytest.mark.asyncio
    async def test_non_reversible_action_routes_to_hitl_under_autonomy(self) -> None:
        # A registered, no-HITL, low-risk but NON-reversible tool must not execute
        # autonomously under HOTL — it falls back to HITL (HITL_NON_REVERSIBLE).
        _set_provider(**{"autonomous-mode-low-risk": True})
        reg = ToolRegistry()
        reg.register(
            ToolDefinition(
                name="auto-task",
                description="a non-reversible automated task",
                version="1.0",
                risk_level=ToolRiskLevel.LOW,
                pii_access=[],
                requires_hitl=False,
                rate_limit_per_minute=60,
                rate_limit_per_hour=1000,
                owner_team="platform",
                reversible=False,  # ← key: non-reversible
                max_hotl_risk_score=0.0,
                allowed_autonomy_levels=("low-risk", "medium-risk", "full"),
            )
        )
        audit = _make_audit()
        gateway = _make_gateway(HITLStatus.APPROVED)
        orchestrator = AgentOrchestrator(
            agent_id="test-agent",
            audit_logger=audit,
            hitl_gateway=gateway,
            llm_client=StubLLMClient(
                json.dumps({"action": "auto-task", "parameters": {}, "risk_score": 0.1})
            ),
            tool_executor=ToolExecutor(audit_logger=audit, registry=reg),
            compensation_registry=CompensationRegistry(registry=reg),
        )

        result = await orchestrator.run(raw_input={"request_text": "Run the task"})

        gateway.submit_for_approval.assert_called_once()
        assert result["oversight_mode"] == "HITL_NON_REVERSIBLE"

    @pytest.mark.asyncio
    async def test_hotl_execution_notifies_and_opens_override_window(self) -> None:
        # A reversible low-risk action under HOTL triggers the monitor: reviewer
        # notification + override window. read-db-record is reversible in the catalog.
        _set_provider(**{"autonomous-mode-low-risk": True})
        audit = _make_audit()
        override = OverrideService(audit_logger=audit)
        monitor = HOTLMonitor(audit_logger=audit, override_service=override)
        gateway = _make_gateway()
        orchestrator = AgentOrchestrator(
            agent_id="test-agent",
            audit_logger=audit,
            hitl_gateway=gateway,
            llm_client=StubLLMClient(
                json.dumps({"action": "read-db-record", "parameters": {}, "risk_score": 0.1})
            ),
            hotl_monitor=monitor,
        )

        result = await orchestrator.run(raw_input={"request_text": "Read the record"})

        assert result["outcome"] == "EXECUTED"
        assert result["oversight_mode"] == "HOTL_LOW_RISK"
        gateway.submit_for_approval.assert_not_called()
        assert "hotl_action_id" in result
        # The override window was opened for the executed action.
        record = override.get(result["hotl_action_id"])
        assert record.status == "ACTIVE"
        assert record.action_type == "read-db-record"
