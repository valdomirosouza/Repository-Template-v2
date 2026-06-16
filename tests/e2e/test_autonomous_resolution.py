"""E2E — CUJ-003 agent autonomous resolution + guardrail-trip path.

CUJ:   CUJ-003 (Agent Autonomous Resolution)
Spec:  specs/ai/agent-design.md, specs/ai/hitl-hotl.md, specs/ai/guardrails.md
ADR:   ADR-0010 (Agent Framework), ADR-0011 (HITL/HOTL Model),
       ADR-0015 (Feature Flag Strategy — autonomy levels)
SLO:   autonomous resolution rate ≥ 80%; agent action success rate ≥ 99.5%
Refs:  #274

Drives the full Perception → Reason → Act journey of CUJ-003 deterministically
and offline:

  Autonomous path (happy path, issue #274 task 1)
    submit low-risk request + autonomy enabled (LOW_RISK) + stubbed LLM returning
    a low-risk action → action EXECUTED under HOTL, NO HITL decision required,
    and an immutable audit record is written.

  Guardrail-trip path (issue #274 task 2)
    submit a request whose content trips the prompt-injection guard → pipeline
    blocks in the Perception phase before the LLM call and does NOT autonomously
    execute (no EXECUTED audit outcome). The orchestrator records the trip via an
    ERROR OTel span (perceive.injection_guard_passed=False) and a structured-log
    warning — it raises before any AuditEvent is written, so no executed-action
    audit record exists for the tripped request (asserted below).

Transport:
  In-process AgentOrchestrator (the CUJ-003 Perception→Reason→Act surface) wired
  with the in-memory fallbacks — StubLLMClient, InMemoryAuditStorage,
  InMemoryHITLStore — plus an OpenFeature InMemoryProvider for autonomy flags.
  No real LLM, Redis, Kafka, PostgreSQL, or flagd is required. All inputs are
  obviously synthetic; no real PII appears in this file.

Test markers: e2e
"""

from __future__ import annotations

import json

import pytest
from openfeature import api
from openfeature.provider.in_memory_provider import InMemoryFlag, InMemoryProvider

from src.agents.hitl_gateway import HITLGateway
from src.agents.hitl_store import InMemoryHITLStore
from src.agents.orchestrator.orchestrator import AgentOrchestrator
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage

# ── OpenFeature autonomy-flag helpers (autonomy levels are global flag state) ──


def _make_bool_flag(enabled: bool) -> InMemoryFlag[bool]:
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
    """Pin OpenFeature to NONE before each test; other modules mutate the global
    provider, so reset for determinism."""
    _all_off()


# ── Builders ──────────────────────────────────────────────────────────────────


def _build_orchestrator(
    llm_response: str,
) -> tuple[AgentOrchestrator, InMemoryAuditStorage]:
    """Wire a real AgentOrchestrator with in-memory fallbacks and a stubbed LLM.

    Returns the orchestrator plus the audit storage so tests can assert the
    write-before-execute audit trail.
    """
    from src.shared.llm_client import StubLLMClient

    storage = InMemoryAuditStorage()
    audit = AuditLogger(storage_backend=storage)
    gateway = HITLGateway(audit_logger=audit, broker=None, store=InMemoryHITLStore())
    orchestrator = AgentOrchestrator(
        agent_id="cuj003-e2e-agent",
        audit_logger=audit,
        hitl_gateway=gateway,
        llm_client=StubLLMClient(llm_response),
    )
    return orchestrator, storage


# "read-db-record" is a registered, low-risk, reversible, no-HITL starter-catalog
# tool — the canonical eligible action for autonomous (HOTL) resolution.
_LOW_RISK_ACTION = json.dumps(
    {"action": "read-db-record", "parameters": {"record_id": "synthetic-0001"}, "risk_score": 0.1}
)


# ── CUJ-003 autonomous-resolution happy path (issue #274 task 1) ──────────────


@pytest.mark.e2e
class TestAutonomousResolution:
    @pytest.mark.asyncio
    async def test_low_risk_request_resolves_without_hitl(self) -> None:
        """Autonomy LOW_RISK + low-risk action → executed under HOTL, no HITL."""
        _set_provider(**{"autonomous-mode-low-risk": True})
        orchestrator, _ = _build_orchestrator(_LOW_RISK_ACTION)

        result = await orchestrator.run(
            raw_input={"request_text": "Show me the synthetic record"},
        )

        # Resolved autonomously — executed, no human-in-the-loop suspension.
        assert result["outcome"] == "EXECUTED"
        assert result["oversight_mode"] == "HOTL_LOW_RISK"
        assert result["autonomy_level"] == "low-risk"
        # Executed autonomously — no human-approval suspension key is present.
        assert result.get("status") != "waiting_for_human_approval"

    @pytest.mark.asyncio
    async def test_autonomous_action_is_audit_logged(self) -> None:
        """Every autonomous action is audit-logged regardless of autonomy (CUJ-003 step 5)."""
        _set_provider(**{"autonomous-mode-low-risk": True})
        orchestrator, storage = _build_orchestrator(_LOW_RISK_ACTION)

        await orchestrator.run(raw_input={"request_text": "Read the synthetic record"})

        events = await storage.query()
        assert len(events) >= 1, "expected at least one audit record for the autonomous action"
        # Write-before-execute invariant: a PENDING (proposed) record precedes
        # the terminal EXECUTED record from the tool executor.
        outcomes = [e.outcome for e in events]
        assert "PENDING" in outcomes
        assert "EXECUTED" in outcomes

    @pytest.mark.asyncio
    async def test_audit_records_reference_the_autonomous_action(self) -> None:
        """The audit trail names the executed action and the eligible agent."""
        _set_provider(**{"autonomous-mode-low-risk": True})
        orchestrator, storage = _build_orchestrator(_LOW_RISK_ACTION)

        await orchestrator.run(raw_input={"request_text": "Read the synthetic record"})

        events = await storage.query()
        assert all(e.agent_id == "cuj003-e2e-agent" for e in events)
        assert any(e.action == "read-db-record" for e in events)

    @pytest.mark.asyncio
    async def test_disabled_autonomy_routes_low_risk_action_to_hitl(self) -> None:
        """With autonomy NONE (default), even a low-risk action requires HITL —
        confirms the autonomous path is genuinely gated by the feature flag."""
        # _reset_autonomy_to_none fixture leaves all flags off.
        orchestrator, _ = _build_orchestrator(_LOW_RISK_ACTION)

        result = await orchestrator.run(
            raw_input={"request_text": "Read the synthetic record"},
        )

        # No autonomy → gateway pends the request; not auto-resolved.
        assert result["outcome"] == "PENDING"
        assert result["status"] == "waiting_for_human_approval"


# ── Guardrail-trip path (issue #274 task 2) ───────────────────────────────────


@pytest.mark.e2e
class TestGuardrailTrip:
    # 80× repetition trips the prompt-injection guard's REPETITIVE_PATTERN rule.
    _INJECTION_INPUT = "SYNTHETIC_INJECT_ATTEMPT " * 80

    @pytest.mark.asyncio
    async def test_injection_input_is_blocked_before_execution(self) -> None:
        """Even with autonomy enabled, an injection input is rejected in Perception
        and never reaches the LLM or autonomous execution."""
        _set_provider(**{"autonomous-mode-low-risk": True})
        orchestrator, _ = _build_orchestrator(_LOW_RISK_ACTION)

        with pytest.raises(ValueError, match="rejected"):
            await orchestrator.run(raw_input={"request_text": self._INJECTION_INPUT})

    @pytest.mark.asyncio
    async def test_injection_does_not_autonomously_execute(self) -> None:
        """The guardrail trip blocks before any tool action is recorded — no
        EXECUTED audit outcome for the tripped request."""
        _set_provider(**{"autonomous-mode-low-risk": True})
        orchestrator, storage = _build_orchestrator(_LOW_RISK_ACTION)

        with pytest.raises(ValueError, match="rejected"):
            await orchestrator.run(raw_input={"request_text": self._INJECTION_INPUT})

        events = await storage.query()
        outcomes = [e.outcome for e in events]
        assert "EXECUTED" not in outcomes, "injection input must not autonomously execute"
