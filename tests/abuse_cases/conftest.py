"""Shared fixtures for abuse case tests.

All tests in this directory use mock LLMs — no real API calls are made.
Tests verify that guardrails, spec contracts, or HITL gateway intercept attacks.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 4 (CV1, CV2)
ADR:  ADR-0050
Issue: #35
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.hitl_gateway import HITLStatus
from src.guardrails.prompt_injection_guard import PromptInjectionGuard


@pytest.fixture()
def injection_guard() -> PromptInjectionGuard:
    return PromptInjectionGuard()


@pytest.fixture()
def mock_audit():
    audit = AsyncMock()
    audit.log_event = AsyncMock()
    return audit


@pytest.fixture()
def mock_hitl_approved():
    """A mock HITL gateway that always approves actions."""
    hitl = AsyncMock()
    approved = MagicMock()
    approved.status = HITLStatus.APPROVED
    hitl.submit_for_approval = AsyncMock(return_value=approved)
    hitl.record_decision = AsyncMock()
    return hitl


@pytest.fixture()
def mock_hitl_rejected():
    """A mock HITL gateway that always rejects actions."""
    hitl = AsyncMock()
    rejected = MagicMock()
    rejected.status = HITLStatus.REJECTED
    hitl.submit_for_approval = AsyncMock(return_value=rejected)
    return hitl


@pytest.fixture()
def mock_llm_clean():
    """Mock LLM that returns a safe, low-risk response."""
    llm = AsyncMock()
    llm.complete = AsyncMock(
        return_value='{"action": "read_file", "parameters": {"path": "/tmp/x"}, "risk_score": 0.1}'
    )
    return llm


def make_orchestrator(llm, audit, hitl, spec_enforcer=None):
    """Build an AgentOrchestrator with mocked dependencies."""
    from src.agents.orchestrator.orchestrator import AgentOrchestrator

    return AgentOrchestrator(
        agent_id="abuse-test-agent",
        audit_logger=audit,
        hitl_gateway=hitl,
        llm_client=llm,
        spec_contract_enforcer=spec_enforcer,
    )
