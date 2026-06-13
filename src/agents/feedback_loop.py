"""Feedback Loop — Telemetria → Comportamento do Agente.

Consome métricas Prometheus de rejeição/aprovação HITL e ajusta dinamicamente
o risk_score_bias por action_type. Fecha o ciclo entre observabilidade e
decisões de risco do HITLGateway.

Spec: specs/ai/feedback-loop.md
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

import httpx

from src.observability.logger import get_logger
from src.observability.metrics import (
    FEEDBACK_ADJUSTMENTS_COUNTER,
    FEEDBACK_BIAS_APPLIED,
    FEEDBACK_REJECTION_RATE,
)
from src.shared.config import settings
from src.shared.url_allowlist import validate_outbound_url

logger = get_logger("feedback_loop")


@dataclass
class ActionStats:
    """Rejection and approval counts for a single action_type."""

    action_type: str
    total: int = 0
    rejections: int = 0
    approvals: int = 0

    @property
    def rejection_rate(self) -> float:
        return self.rejections / self.total if self.total > 0 else 0.0

    @property
    def approval_rate(self) -> float:
        return self.approvals / self.total if self.total > 0 else 0.0


@dataclass
class BiasAdjustment:
    """Record of a single bias change applied by the feedback loop."""

    action_type: str
    previous_bias: float
    new_bias: float
    reason: str

    @property
    def direction(self) -> str:
        return "up" if self.new_bias > self.previous_bias else "down"


class FeedbackLoop:
    """Telemetry-driven risk bias adjuster for the HITL Gateway.

    Runs as an asyncio background task. On each cycle it:
    1. Queries Prometheus for HITL approval/rejection counters.
    2. Computes per-action_type rejection rates.
    3. Adjusts the in-memory bias table (and publishes to Kafka).
    4. Updates Prometheus gauges for the Grafana dashboard.

    The HITLGateway (or orchestrator) calls ``get_bias(action_type)`` to obtain
    the current adjustment before evaluating a request's effective risk score:
    ``effective_risk = min(1.0, raw_risk + feedback_loop.get_bias(action_type))``.
    """

    def __init__(
        self,
        broker: Any | None = None,
        prometheus_url: str | None = None,
    ) -> None:
        self._broker = broker
        self._prometheus_url = prometheus_url or settings.feedback_prometheus_url
        self._biases: dict[str, float] = {}
        self._lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────────────────

    def get_bias(self, action_type: str) -> float:
        """Return the current risk_score bias for *action_type* (0.0 if unknown)."""
        return self._biases.get(action_type, 0.0)

    async def run_once(self) -> list[BiasAdjustment]:
        """Execute one feedback cycle and return all adjustments made."""
        try:
            stats = await self._collect_rejection_rates()
        except Exception as exc:
            logger.warning("feedback loop: Prometheus query failed", error=str(exc))
            return []

        adjustments: list[BiasAdjustment] = []
        for _action_type, s in stats.items():
            adj = await self._maybe_adjust(s)
            if adj is not None:
                adjustments.append(adj)
                await self._publish(adj)

        return adjustments

    async def run(self) -> None:
        """Background loop — runs indefinitely until cancelled."""
        logger.info(
            "feedback loop started",
            interval_seconds=settings.feedback_loop_interval_seconds,
        )
        while True:
            adjustments = await self.run_once()
            if adjustments:
                logger.info(
                    "feedback loop: applied adjustments",
                    count=len(adjustments),
                    adjustments=[
                        {
                            "action_type": a.action_type,
                            "direction": a.direction,
                            "new_bias": a.new_bias,
                        }
                        for a in adjustments
                    ],
                )
            await asyncio.sleep(settings.feedback_loop_interval_seconds)

    # ── Prometheus collection ───────────────────────────────────────────────────

    async def _collect_rejection_rates(self) -> dict[str, ActionStats]:
        """Query Prometheus for HITL counters and return per-action_type stats."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            approvals = await self._query(client, "hitl_approvals_total")
            rejections = await self._query(client, "hitl_rejections_total")

        stats: dict[str, ActionStats] = {}

        for result in approvals:
            action_type = result["metric"].get("action_type", "unknown")
            count = int(float(result["value"][1]))
            s = stats.setdefault(action_type, ActionStats(action_type=action_type))
            s.approvals += count
            s.total += count

        for result in rejections:
            action_type = result["metric"].get("action_type", "unknown")
            count = int(float(result["value"][1]))
            s = stats.setdefault(action_type, ActionStats(action_type=action_type))
            s.rejections += count
            s.total += count

        for action_type, s in stats.items():
            FEEDBACK_REJECTION_RATE.labels(action_type).set(s.rejection_rate)

        return stats

    async def _query(self, client: httpx.AsyncClient, metric: str) -> list[dict[str, Any]]:
        """Run an instant PromQL query and return the result list."""
        # A10/SSRF: validate the outbound target before the request (config-derived here, but the
        # allow-list is enforced at every HTTP-client boundary as a matter of policy).
        target = validate_outbound_url(f"{self._prometheus_url}/api/v1/query")
        resp = await client.get(
            target,
            params={"query": f"sum by (action_type) ({metric})"},
        )
        resp.raise_for_status()
        data = resp.json()
        return cast(list[dict[str, Any]], data.get("data", {}).get("result", []))

    # ── Bias adjustment ─────────────────────────────────────────────────────────

    async def _maybe_adjust(self, stats: ActionStats) -> BiasAdjustment | None:
        """Apply or remove bias for one action_type. Returns the adjustment or None."""
        if stats.total < settings.feedback_min_samples:
            return None

        async with self._lock:
            current = self._biases.get(stats.action_type, 0.0)

            if stats.rejection_rate > settings.feedback_rejection_threshold:
                new_bias = min(
                    settings.feedback_bias_max,
                    current + settings.feedback_bias_step_up,
                )
                reason = (
                    f"rejection_rate={stats.rejection_rate:.2%} "
                    f"> threshold={settings.feedback_rejection_threshold:.2%}"
                )
            elif stats.approval_rate > settings.feedback_approval_threshold and current > 0.0:
                new_bias = max(0.0, current - settings.feedback_bias_step_down)
                reason = (
                    f"approval_rate={stats.approval_rate:.2%} "
                    f"> threshold={settings.feedback_approval_threshold:.2%}"
                )
            else:
                return None

            if new_bias == current:
                return None

            self._biases[stats.action_type] = new_bias

        adj = BiasAdjustment(
            action_type=stats.action_type,
            previous_bias=current,
            new_bias=new_bias,
            reason=reason,
        )

        FEEDBACK_BIAS_APPLIED.labels(stats.action_type).set(new_bias)
        FEEDBACK_ADJUSTMENTS_COUNTER.labels(stats.action_type, adj.direction).inc()

        logger.info(
            "feedback loop: bias adjusted",
            action_type=stats.action_type,
            previous=current,
            new=new_bias,
            direction=adj.direction,
            reason=reason,
        )
        return adj

    # ── Kafka publish ───────────────────────────────────────────────────────────

    async def _publish(self, adj: BiasAdjustment) -> None:
        if self._broker is None:
            return
        try:
            import uuid
            from datetime import UTC, datetime

            await self._broker.publish(
                "agent.feedback.applied",
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "agent.feedback.applied",
                    "schema_version": "1.0",
                    "produced_at": datetime.now(UTC).isoformat(),
                    "trace_id": None,
                    "producer_service": settings.service_name,
                    "payload": {
                        "action_type": adj.action_type,
                        "previous_bias": adj.previous_bias,
                        "new_bias": adj.new_bias,
                        "direction": adj.direction,
                        "reason": adj.reason,
                    },
                },
            )
        except Exception as exc:
            logger.warning("feedback loop: broker publish failed", error=str(exc))
