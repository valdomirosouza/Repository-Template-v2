"""Unit tests for FeedbackLoop.

Spec: specs/ai/feedback-loop.md
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.feedback_loop import (
    ActionStats,
    BiasAdjustment,
    FeedbackLoop,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_loop(broker=None) -> FeedbackLoop:
    return FeedbackLoop(broker=broker, prometheus_url="http://prometheus:9090")


def _stats(action_type: str, approvals: int, rejections: int) -> ActionStats:
    s = ActionStats(action_type=action_type)
    s.approvals = approvals
    s.rejections = rejections
    s.total = approvals + rejections
    return s


# ── ActionStats ───────────────────────────────────────────────────────────────


class TestActionStats:
    def test_rejection_rate_zero_when_no_data(self):
        s = ActionStats(action_type="deploy")
        assert s.rejection_rate == 0.0

    def test_rejection_rate_calculated(self):
        s = _stats("deploy", approvals=7, rejections=3)
        assert s.rejection_rate == pytest.approx(0.3)

    def test_approval_rate_calculated(self):
        s = _stats("deploy", approvals=7, rejections=3)
        assert s.approval_rate == pytest.approx(0.7)

    def test_rates_sum_to_one(self):
        s = _stats("write_file", approvals=6, rejections=4)
        assert s.rejection_rate + s.approval_rate == pytest.approx(1.0)


# ── BiasAdjustment ────────────────────────────────────────────────────────────


class TestBiasAdjustment:
    def test_direction_up(self):
        adj = BiasAdjustment(action_type="x", previous_bias=0.1, new_bias=0.2, reason="test")
        assert adj.direction == "up"

    def test_direction_down(self):
        adj = BiasAdjustment(action_type="x", previous_bias=0.2, new_bias=0.1, reason="test")
        assert adj.direction == "down"


# ── get_bias ──────────────────────────────────────────────────────────────────


class TestGetBias:
    def test_returns_zero_for_unknown_action(self):
        loop = _make_loop()
        assert loop.get_bias("never_seen") == 0.0

    def test_returns_stored_bias(self):
        loop = _make_loop()
        loop._biases["deploy"] = 0.2
        assert loop.get_bias("deploy") == pytest.approx(0.2)


# ── _maybe_adjust ─────────────────────────────────────────────────────────────


class TestMaybeAdjust:
    @pytest.mark.asyncio
    async def test_no_adjustment_below_min_samples(self):
        loop = _make_loop()
        # 5 rejections out of 9 total — high rejection rate but < min_samples=10
        s = _stats("deploy", approvals=4, rejections=5)
        with patch("src.agents.feedback_loop.settings") as cfg:
            cfg.feedback_min_samples = 10
            cfg.feedback_rejection_threshold = 0.30
            cfg.feedback_approval_threshold = 0.80
            cfg.feedback_bias_step_up = 0.10
            cfg.feedback_bias_step_down = 0.05
            cfg.feedback_bias_max = 0.50
            result = await loop._maybe_adjust(s)
        assert result is None
        assert loop.get_bias("deploy") == 0.0

    @pytest.mark.asyncio
    async def test_bias_increases_on_high_rejection(self):
        loop = _make_loop()
        s = _stats("deploy", approvals=6, rejections=4)  # 40% rejection > 30% threshold
        with patch("src.agents.feedback_loop.settings") as cfg:
            cfg.feedback_min_samples = 10
            cfg.feedback_rejection_threshold = 0.30
            cfg.feedback_approval_threshold = 0.80
            cfg.feedback_bias_step_up = 0.10
            cfg.feedback_bias_step_down = 0.05
            cfg.feedback_bias_max = 0.50
            result = await loop._maybe_adjust(s)
        assert result is not None
        assert result.direction == "up"
        assert result.new_bias == pytest.approx(0.10)
        assert loop.get_bias("deploy") == pytest.approx(0.10)

    @pytest.mark.asyncio
    async def test_bias_capped_at_maximum(self):
        loop = _make_loop()
        loop._biases["deploy"] = 0.45  # already near cap
        s = _stats("deploy", approvals=3, rejections=7)  # 70% rejection
        with patch("src.agents.feedback_loop.settings") as cfg:
            cfg.feedback_min_samples = 10
            cfg.feedback_rejection_threshold = 0.30
            cfg.feedback_approval_threshold = 0.80
            cfg.feedback_bias_step_up = 0.10
            cfg.feedback_bias_step_down = 0.05
            cfg.feedback_bias_max = 0.50
            result = await loop._maybe_adjust(s)
        assert result is not None
        assert result.new_bias == pytest.approx(0.50)  # capped at 0.50, not 0.55

    @pytest.mark.asyncio
    async def test_bias_decreases_on_high_approval(self):
        loop = _make_loop()
        loop._biases["read_file"] = 0.20  # existing positive bias
        s = _stats("read_file", approvals=90, rejections=10)  # 90% approval > 80% threshold
        with patch("src.agents.feedback_loop.settings") as cfg:
            cfg.feedback_min_samples = 10
            cfg.feedback_rejection_threshold = 0.30
            cfg.feedback_approval_threshold = 0.80
            cfg.feedback_bias_step_up = 0.10
            cfg.feedback_bias_step_down = 0.05
            cfg.feedback_bias_max = 0.50
            result = await loop._maybe_adjust(s)
        assert result is not None
        assert result.direction == "down"
        assert result.new_bias == pytest.approx(0.15)

    @pytest.mark.asyncio
    async def test_bias_floor_at_zero(self):
        loop = _make_loop()
        loop._biases["read_file"] = 0.03  # very small existing bias
        s = _stats("read_file", approvals=95, rejections=5)
        with patch("src.agents.feedback_loop.settings") as cfg:
            cfg.feedback_min_samples = 10
            cfg.feedback_rejection_threshold = 0.30
            cfg.feedback_approval_threshold = 0.80
            cfg.feedback_bias_step_up = 0.10
            cfg.feedback_bias_step_down = 0.05
            cfg.feedback_bias_max = 0.50
            result = await loop._maybe_adjust(s)
        assert result is not None
        assert result.new_bias == pytest.approx(0.0)  # floored at 0, not -0.02

    @pytest.mark.asyncio
    async def test_no_adjustment_when_already_zero_and_high_approval(self):
        loop = _make_loop()
        # bias is 0 already — no reason to go negative
        s = _stats("read_file", approvals=90, rejections=10)
        with patch("src.agents.feedback_loop.settings") as cfg:
            cfg.feedback_min_samples = 10
            cfg.feedback_rejection_threshold = 0.30
            cfg.feedback_approval_threshold = 0.80
            cfg.feedback_bias_step_up = 0.10
            cfg.feedback_bias_step_down = 0.05
            cfg.feedback_bias_max = 0.50
            result = await loop._maybe_adjust(s)
        assert result is None  # bias is 0.0, current == new_bias → no adjustment

    @pytest.mark.asyncio
    async def test_no_adjustment_in_normal_range(self):
        loop = _make_loop()
        s = _stats("deploy", approvals=75, rejections=25)  # 25% rejection < 30% threshold
        with patch("src.agents.feedback_loop.settings") as cfg:
            cfg.feedback_min_samples = 10
            cfg.feedback_rejection_threshold = 0.30
            cfg.feedback_approval_threshold = 0.80
            cfg.feedback_bias_step_up = 0.10
            cfg.feedback_bias_step_down = 0.05
            cfg.feedback_bias_max = 0.50
            result = await loop._maybe_adjust(s)
        assert result is None


# ── _collect_rejection_rates ──────────────────────────────────────────────────


class TestCollectRejectionRates:
    @pytest.mark.asyncio
    async def test_parses_prometheus_response(self):
        loop = _make_loop()

        approval_response = {
            "data": {
                "result": [
                    {"metric": {"action_type": "deploy"}, "value": [0, "8"]},
                    {"metric": {"action_type": "write_file"}, "value": [0, "5"]},
                ]
            }
        }
        rejection_response = {
            "data": {
                "result": [
                    {"metric": {"action_type": "deploy"}, "value": [0, "2"]},
                ]
            }
        }

        mock_approvals = MagicMock()
        mock_approvals.json.return_value = approval_response
        mock_approvals.raise_for_status = MagicMock()

        mock_rejections = MagicMock()
        mock_rejections.json.return_value = rejection_response
        mock_rejections.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_approvals, mock_rejections])

        with patch("httpx.AsyncClient") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            stats = await loop._collect_rejection_rates()

        assert "deploy" in stats
        assert stats["deploy"].approvals == 8
        assert stats["deploy"].rejections == 2
        assert stats["deploy"].total == 10
        assert stats["deploy"].rejection_rate == pytest.approx(0.2)

        assert "write_file" in stats
        assert stats["write_file"].approvals == 5
        assert stats["write_file"].rejections == 0

    @pytest.mark.asyncio
    async def test_returns_empty_on_empty_prometheus(self):
        loop = _make_loop()
        empty = {"data": {"result": []}}

        mock_resp = MagicMock()
        mock_resp.json.return_value = empty
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            stats = await loop._collect_rejection_rates()

        assert stats == {}


# ── run_once ─────────────────────────────────────────────────────────────────


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_returns_adjustments_on_high_rejection(self):
        loop = _make_loop()
        stats = {"deploy": _stats("deploy", approvals=5, rejections=5)}  # 50% rejection

        with patch.object(loop, "_collect_rejection_rates", AsyncMock(return_value=stats)):
            with patch("src.agents.feedback_loop.settings") as cfg:
                cfg.feedback_min_samples = 10
                cfg.feedback_rejection_threshold = 0.30
                cfg.feedback_approval_threshold = 0.80
                cfg.feedback_bias_step_up = 0.10
                cfg.feedback_bias_step_down = 0.05
                cfg.feedback_bias_max = 0.50
                adjustments = await loop.run_once()

        assert len(adjustments) == 1
        assert adjustments[0].action_type == "deploy"
        assert adjustments[0].direction == "up"

    @pytest.mark.asyncio
    async def test_returns_empty_on_prometheus_failure(self):
        loop = _make_loop()
        with patch.object(
            loop, "_collect_rejection_rates", AsyncMock(side_effect=Exception("connection refused"))
        ):
            adjustments = await loop.run_once()
        assert adjustments == []

    @pytest.mark.asyncio
    async def test_publishes_to_broker_on_adjustment(self):
        broker = MagicMock()
        broker.publish = AsyncMock()
        loop = _make_loop(broker=broker)
        stats = {"write_file": _stats("write_file", approvals=3, rejections=7)}

        with patch.object(loop, "_collect_rejection_rates", AsyncMock(return_value=stats)):
            with patch("src.agents.feedback_loop.settings") as cfg:
                cfg.feedback_min_samples = 10
                cfg.feedback_rejection_threshold = 0.30
                cfg.feedback_approval_threshold = 0.80
                cfg.feedback_bias_step_up = 0.10
                cfg.feedback_bias_step_down = 0.05
                cfg.feedback_bias_max = 0.50
                cfg.service_name = "test-service"
                await loop.run_once()

        broker.publish.assert_called_once()
        topic, payload = broker.publish.call_args[0]
        assert topic == "agent.feedback.applied"
        assert payload["payload"]["action_type"] == "write_file"
        assert payload["payload"]["direction"] == "up"

    @pytest.mark.asyncio
    async def test_no_publish_when_no_broker(self):
        loop = _make_loop(broker=None)
        stats = {"deploy": _stats("deploy", approvals=3, rejections=7)}

        with patch.object(loop, "_collect_rejection_rates", AsyncMock(return_value=stats)):
            with patch("src.agents.feedback_loop.settings") as cfg:
                cfg.feedback_min_samples = 10
                cfg.feedback_rejection_threshold = 0.30
                cfg.feedback_approval_threshold = 0.80
                cfg.feedback_bias_step_up = 0.10
                cfg.feedback_bias_step_down = 0.05
                cfg.feedback_bias_max = 0.50
                adjustments = await loop.run_once()

        assert len(adjustments) == 1  # adjustment still made, just not published
