"""Unit tests for src/agents/orchestrator/orchestrator.py.

Spec: specs/ai/agent-design.md
ADR:  ADR-0010 (Agent Framework Selection), ADR-0011 (HITL/HOTL Model)

All test inputs use clearly synthetic, obviously fake data.
No real personal data appears in this file.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.hitl_gateway import HITLStatus
from src.agents.orchestrator.orchestrator import AgentOrchestrator
from src.guardrails.audit_logger import AuditWriteError
from src.shared.llm_client import StubLLMClient


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
        llm_response = json.dumps({"action": "summarise", "parameters": {}, "risk_score": 0.1})
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
        # computed score. "send_report" scores 0.7 irreversibility (write-like action)
        # → 0.35×0.7 + 0.25×0.2 + 0.20×0.1 = 0.315.
        llm_json = json.dumps(
            {"action": "send_report", "parameters": {"to": "team"}, "risk_score": 0.2}
        )
        orchestrator = _make_orchestrator(llm_response=llm_json)

        result = await orchestrator.run(raw_input={"request_text": "Generate weekly report"})

        assert result["action"] == "send_report"
        assert result["risk_score"] == pytest.approx(0.315)

    @pytest.mark.asyncio
    async def test_invalid_llm_json_defaults_to_safe_values(self) -> None:
        # Unparseable LLM output → action="unknown". RiskScorer computes 0.245
        # (unknown action scores 0.5 irreversibility, no external/scale/PII signals).
        orchestrator = _make_orchestrator(llm_response="not valid json {{{{")

        result = await orchestrator.run(raw_input={"request_text": "Do something"})

        assert result["action"] == "unknown"
        assert result["risk_score"] == pytest.approx(0.245)

    @pytest.mark.asyncio
    async def test_missing_risk_score_uses_risk_scorer(self) -> None:
        # LLM omits risk_score — RiskScorer computes based on action+parameters.
        # "test_action" with empty params → 0.5 irreversibility, 0.2 external, 0.1 scale
        # → 0.35×0.5 + 0.25×0.2 + 0.20×0.1 = 0.245.
        llm_json = json.dumps({"action": "test_action", "parameters": {}})
        orchestrator = _make_orchestrator(llm_response=llm_json)

        result = await orchestrator.run(raw_input={"request_text": "Run test"})

        assert result["risk_score"] == pytest.approx(0.245)

    @pytest.mark.asyncio
    async def test_parameters_passed_through_to_result(self) -> None:
        llm_json = json.dumps(
            {"action": "analyse", "parameters": {"depth": "full"}, "risk_score": 0.1}
        )
        orchestrator = _make_orchestrator(llm_response=llm_json)

        result = await orchestrator.run(raw_input={"request_text": "Analyse data"})

        assert result["parameters"] == {"depth": "full"}


class TestAct:
    @pytest.mark.asyncio
    async def test_low_risk_executes_without_hitl(self) -> None:
        # risk_score=0.1 is below the 0.4 hitl_risk_threshold
        llm_json = json.dumps({"action": "read_summary", "parameters": {}, "risk_score": 0.1})
        gateway = _make_gateway()
        orchestrator = AgentOrchestrator(
            agent_id="test-agent",
            audit_logger=_make_audit(),
            hitl_gateway=gateway,
            llm_client=StubLLMClient(llm_json),
        )

        result = await orchestrator.run(raw_input={"request_text": "Show me the summary"})

        assert result["outcome"] == "EXECUTED"
        gateway.submit_for_approval.assert_not_called()

    @pytest.mark.asyncio
    async def test_high_risk_routes_to_hitl(self) -> None:
        # risk_score=0.9 is above the 0.4 threshold
        llm_json = json.dumps({"action": "delete_records", "parameters": {}, "risk_score": 0.9})
        gateway = _make_gateway(HITLStatus.APPROVED)
        orchestrator = AgentOrchestrator(
            agent_id="test-agent",
            audit_logger=_make_audit(),
            hitl_gateway=gateway,
            llm_client=StubLLMClient(llm_json),
        )

        result = await orchestrator.run(raw_input={"request_text": "Clean up old records"})

        gateway.submit_for_approval.assert_called_once()
        assert result["outcome"] == "EXECUTED"

    @pytest.mark.asyncio
    async def test_hitl_rejection_raises_value_error(self) -> None:
        llm_json = json.dumps({"action": "delete_records", "parameters": {}, "risk_score": 0.9})
        orchestrator = _make_orchestrator(
            llm_response=llm_json,
            gateway_status=HITLStatus.REJECTED,
        )

        with pytest.raises(ValueError, match="rejected"):
            await orchestrator.run(raw_input={"request_text": "Delete all records"})

    @pytest.mark.asyncio
    async def test_audit_write_error_blocks_action(self) -> None:
        llm_json = json.dumps({"action": "summarise", "parameters": {}, "risk_score": 0.1})
        audit = _make_audit(side_effect=AuditWriteError("disk full"))
        orchestrator = _make_orchestrator(llm_response=llm_json, audit=audit)

        with pytest.raises(AuditWriteError):
            await orchestrator.run(raw_input={"request_text": "Summarise logs"})

    @pytest.mark.asyncio
    async def test_pending_audit_written_before_executed(self) -> None:
        # Write-before-execute invariant: first call must be PENDING, second EXECUTED
        llm_json = json.dumps({"action": "summarise", "parameters": {}, "risk_score": 0.1})
        audit = _make_audit()
        orchestrator = _make_orchestrator(llm_response=llm_json, audit=audit)

        await orchestrator.run(raw_input={"request_text": "Summarise logs"})

        assert audit.log_event.call_count == 2
        first_event = audit.log_event.call_args_list[0][0][0]
        second_event = audit.log_event.call_args_list[1][0][0]
        assert first_event.outcome == "PENDING"
        assert second_event.outcome == "EXECUTED"

    @pytest.mark.asyncio
    async def test_result_contains_expected_fields(self) -> None:
        llm_json = json.dumps(
            {"action": "analyse", "parameters": {"depth": "full"}, "risk_score": 0.2}
        )
        orchestrator = _make_orchestrator(llm_response=llm_json)

        result = await orchestrator.run(
            raw_input={"request_text": "Analyse data"},
            trace_id="trace-unit-xyz",
        )

        assert result["agent_id"] == "test-orchestrator"
        assert result["action"] == "analyse"
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
