"""Unit tests for HITLGateway — eviction and hard cap (Wave 2).

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.hitl_gateway import (
    HITLDecision,
    HITLGateway,
    HITLGatewayError,
    HITLRequest,
    HITLStatus,
)
from src.agents.hitl_store import InMemoryHITLStore

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_gateway(max_pending: int = 500) -> HITLGateway:
    audit = MagicMock()
    audit.log_event = AsyncMock()
    store = InMemoryHITLStore()
    gw = HITLGateway(audit_logger=audit, broker=None, store=store)
    import src.agents.hitl_gateway as mod

    mod.settings.hitl_max_pending_requests = max_pending
    return gw


def _make_request(agent_id: str = "agent-test") -> HITLRequest:
    now = datetime.now(UTC)
    return HITLRequest(
        request_id=str(uuid.uuid4()),
        agent_id=agent_id,
        action_type="test_action",
        action_parameters={},
        risk_score=0.8,
        context_summary="synthetic context",
        created_at=now,
        expires_at=now + timedelta(seconds=3600),
    )


# ── Init ──────────────────────────────────────────────────────────────────────


class TestHITLGatewayInit:
    def test_default_store_created_when_none_supplied(self):
        from src.agents.hitl_store import InMemoryHITLStore

        audit = MagicMock()
        audit.log_event = AsyncMock()
        gw = HITLGateway(audit_logger=audit, broker=None)
        assert isinstance(gw._store, InMemoryHITLStore)


# ── Hard cap ──────────────────────────────────────────────────────────────────


class TestHITLGatewayHardCap:
    @pytest.mark.asyncio
    async def test_submit_raises_when_store_at_capacity(self):
        gw = _make_gateway(max_pending=2)

        req1 = _make_request()
        req2 = _make_request()
        req3 = _make_request()

        await gw.submit_for_approval(req1)
        await gw.submit_for_approval(req2)

        with pytest.raises(HITLGatewayError, match="capacity"):
            await gw.submit_for_approval(req3)

    @pytest.mark.asyncio
    async def test_submit_succeeds_when_below_capacity(self):
        gw = _make_gateway(max_pending=5)
        req = _make_request()
        result = await gw.submit_for_approval(req)
        assert result.status == HITLStatus.PENDING

    @pytest.mark.asyncio
    async def test_store_count_is_correct_after_submit(self):
        gw = _make_gateway(max_pending=10)
        for _ in range(3):
            await gw.submit_for_approval(_make_request())
        assert await gw._store.pending_count() == 3


# ── Eviction ──────────────────────────────────────────────────────────────────


class TestHITLGatewayEviction:
    @pytest.mark.asyncio
    async def test_expire_stale_requests_evicts_from_store(self):
        gw = _make_gateway()
        now = datetime.now(UTC)

        req = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="agent-x",
            action_type="act",
            action_parameters={},
            risk_score=0.5,
            context_summary="ctx",
            created_at=now - timedelta(seconds=7200),
            expires_at=now - timedelta(seconds=3600),  # already expired
        )
        await gw._store.save(req)

        expired = await gw.expire_stale_requests()

        assert req.request_id in expired
        assert await gw._store.get_active(req.request_id) is None

    @pytest.mark.asyncio
    async def test_expire_stale_requests_does_not_evict_pending_valid(self):
        gw = _make_gateway()
        req = _make_request()  # expires in 1 hour
        await gw._store.save(req)

        expired = await gw.expire_stale_requests()

        assert req.request_id not in expired
        assert await gw._store.get_active(req.request_id) is not None

    @pytest.mark.asyncio
    async def test_eviction_frees_slot_for_new_request(self):
        gw = _make_gateway(max_pending=1)
        now = datetime.now(UTC)

        expired_req = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="agent-y",
            action_type="act",
            action_parameters={},
            risk_score=0.5,
            context_summary="ctx",
            created_at=now - timedelta(seconds=7200),
            expires_at=now - timedelta(seconds=1),
        )
        await gw._store.save(expired_req)

        # Store is full (1/1), but after eviction there is room
        await gw.expire_stale_requests()

        new_req = _make_request()
        result = await gw.submit_for_approval(new_req)
        assert result.status == HITLStatus.PENDING

    @pytest.mark.asyncio
    async def test_expired_request_status_is_set_to_expired(self):
        gw = _make_gateway()
        now = datetime.now(UTC)

        req = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="agent-z",
            action_type="act",
            action_parameters={},
            risk_score=0.5,
            context_summary="ctx",
            created_at=now - timedelta(seconds=7200),
            expires_at=now - timedelta(seconds=1),
        )
        await gw._store.save(req)

        await gw.expire_stale_requests()

        assert req.status == HITLStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_expired_request_still_retrievable_via_get_request(self):
        gw = _make_gateway()
        now = datetime.now(UTC)

        req = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="agent-a",
            action_type="act",
            action_parameters={},
            risk_score=0.5,
            context_summary="ctx",
            created_at=now - timedelta(seconds=7200),
            expires_at=now - timedelta(seconds=1),
        )
        await gw._store.save(req)

        await gw.expire_stale_requests()

        retrieved = await gw.get_request(req.request_id)
        assert retrieved is not None
        assert retrieved.status == HITLStatus.EXPIRED
        assert await gw._store.get_active(req.request_id) is None
        assert await gw._store.get(req.request_id) is not None

    @pytest.mark.asyncio
    async def test_mid_decision_expiry_moves_request_to_expired_store(self):
        gw = _make_gateway()
        now = datetime.now(UTC)

        req = HITLRequest(
            request_id=str(uuid.uuid4()),
            agent_id="agent-b",
            action_type="act",
            action_parameters={},
            risk_score=0.5,
            context_summary="ctx",
            created_at=now - timedelta(seconds=7200),
            expires_at=now - timedelta(seconds=1),
        )
        await gw._store.save(req)

        with pytest.raises(HITLGatewayError, match="expired"):
            await gw.record_decision(
                HITLDecision(
                    request_id=req.request_id,
                    decision=HITLStatus.APPROVED,
                    approver_id="reviewer-01",
                    rationale="Late.",
                    decided_at=now,
                )
            )

        assert await gw._store.get_active(req.request_id) is None
        assert await gw._store.get(req.request_id) is not None


# ── Gauge ─────────────────────────────────────────────────────────────────────


class TestHITLGatewayGauge:
    @pytest.mark.asyncio
    async def test_gauge_decrements_on_approved_decision(self):
        from unittest.mock import MagicMock, patch

        gw = _make_gateway()
        req = _make_request()
        now = datetime.now(UTC)

        with patch("src.agents.hitl_gateway.ACTIVE_HITL_REQUESTS") as mock_gauge:
            mock_labels = MagicMock()
            mock_gauge.labels.return_value = mock_labels

            await gw.submit_for_approval(req)
            await gw.record_decision(
                HITLDecision(
                    request_id=req.request_id,
                    decision=HITLStatus.APPROVED,
                    approver_id="reviewer-01",
                    rationale="Approved.",
                    decided_at=now,
                )
            )

            mock_labels.inc.assert_called_once()
            mock_labels.dec.assert_called_once()

    @pytest.mark.asyncio
    async def test_gauge_decrements_on_rejected_decision(self):
        from unittest.mock import MagicMock, patch

        gw = _make_gateway()
        req = _make_request()
        now = datetime.now(UTC)

        with patch("src.agents.hitl_gateway.ACTIVE_HITL_REQUESTS") as mock_gauge:
            mock_labels = MagicMock()
            mock_gauge.labels.return_value = mock_labels

            await gw.submit_for_approval(req)
            await gw.record_decision(
                HITLDecision(
                    request_id=req.request_id,
                    decision=HITLStatus.REJECTED,
                    approver_id="reviewer-01",
                    rationale="Rejected.",
                    decided_at=now,
                )
            )

            mock_labels.inc.assert_called_once()
            mock_labels.dec.assert_called_once()


# ── Archive ───────────────────────────────────────────────────────────────────


class TestHITLGatewayArchive:
    @pytest.mark.asyncio
    async def test_approved_request_archived(self):
        gw = _make_gateway()
        req = _make_request()
        now = datetime.now(UTC)

        await gw.submit_for_approval(req)
        await gw.record_decision(
            HITLDecision(
                request_id=req.request_id,
                decision=HITLStatus.APPROVED,
                approver_id="reviewer-01",
                rationale="Approved.",
                decided_at=now,
            )
        )

        assert await gw._store.get_active(req.request_id) is None
        retrieved = await gw._store.get(req.request_id)
        assert retrieved is not None
        assert retrieved.status == HITLStatus.APPROVED

    @pytest.mark.asyncio
    async def test_rejected_request_archived(self):
        gw = _make_gateway()
        req = _make_request()
        now = datetime.now(UTC)

        await gw.submit_for_approval(req)
        await gw.record_decision(
            HITLDecision(
                request_id=req.request_id,
                decision=HITLStatus.REJECTED,
                approver_id="reviewer-01",
                rationale="Rejected.",
                decided_at=now,
            )
        )

        assert await gw._store.get_active(req.request_id) is None
        retrieved = await gw._store.get(req.request_id)
        assert retrieved is not None
        assert retrieved.status == HITLStatus.REJECTED

    @pytest.mark.asyncio
    async def test_pending_count_decrements_after_decision(self):
        gw = _make_gateway(max_pending=10)
        req1 = _make_request()
        req2 = _make_request()
        now = datetime.now(UTC)

        await gw.submit_for_approval(req1)
        await gw.submit_for_approval(req2)
        assert await gw._store.pending_count() == 2

        await gw.record_decision(
            HITLDecision(
                request_id=req1.request_id,
                decision=HITLStatus.APPROVED,
                approver_id="reviewer-01",
                rationale="Approved.",
                decided_at=now,
            )
        )

        assert await gw._store.pending_count() == 1
