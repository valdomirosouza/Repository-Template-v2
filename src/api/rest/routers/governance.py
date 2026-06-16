"""Read-only SLO-status endpoint for the operator UI SLO / error-budget panel.

Flow: GET /v1/governance/slo-status → parse (cached) docs/sre/slo/slo.yaml → for each SLO
attach an HONEST ``observed`` block: a real in-process Prometheus sample where one can be cleanly
read (api-gateway availability/error-rate), otherwise ``data_available: false`` with a note.

Honesty (CLAUDE.md §3.6): the app has no metrics-query (PromQL) layer, so 30-day SLO compliance /
burn-rate cannot be computed here. We return the real SLO *targets* from the yaml and never
fabricate observed numbers. See specs/api/SPEC-API-004-runs-trace-and-slo-status.md §9.1.

Spec: specs/api/SPEC-API-004-runs-trace-and-slo-status.md
ADR:  ADR-0076 (structured error model), ADR-0004 (observability — Prometheus + slo.yaml)
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.rest.auth import Principal, get_principal
from src.observability.logger import get_logger
from src.observability.metrics import REQUEST_COUNTER

logger = get_logger("api.governance")
router = APIRouter(tags=["governance"])

# Repo-root-relative path to the SLO definitions (this file is src/api/rest/routers/governance.py).
_SLO_PATH = Path(__file__).resolve().parents[4] / "docs" / "sre" / "slo" / "slo.yaml"

# SLOs for which a real in-process observed value can be cleanly read from http_requests_total.
_API_GATEWAY_SERVICE = "api-gateway"
_OBSERVABLE_API_SLOS = {"availability", "error_rate"}


# ── Schemas ───────────────────────────────────────────────────────────────────


class SLOObserved(BaseModel):
    """Honest observed block. When a real value cannot be computed, ``data_available`` is False
    and ``note`` explains why — a number is NEVER fabricated (CLAUDE.md §3.6)."""

    data_available: bool
    value: float | None = None
    unit: str | None = None
    source: str | None = None
    scope: str | None = None
    note: str | None = None


class SLOItemStatus(BaseModel):
    name: str
    sli_type: str
    description: str | None = None
    target: float | None = None
    target_ms: float | None = None
    target_max: float | None = None
    window: str | None = None
    observed: SLOObserved


class SLOServiceStatus(BaseModel):
    name: str
    description: str | None = None
    slos: list[SLOItemStatus] = Field(default_factory=list)


class SLOStatusResponse(BaseModel):
    """SLO targets + honest observed status for the operator UI panel (SPEC-API-004)."""

    source_version: str | None = None
    generated_at: datetime
    services: list[SLOServiceStatus] = Field(default_factory=list)


# ── SLO file loading (cached) ──────────────────────────────────────────────────


@lru_cache(maxsize=1)
def load_slo_definitions() -> dict[str, Any]:
    """Parse docs/sre/slo/slo.yaml once and cache it in-process (NFR-02)."""
    with _SLO_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


# ── Honest observed computation ─────────────────────────────────────────────────


def _api_gateway_non5xx_ratio() -> float | None:
    """Compute the share of non-5xx api-gateway responses from the in-process counter.

    Returns a fraction in [0, 1], or ``None`` when the counter has no samples yet (so the
    caller can flag ``data_available: false`` instead of dividing by zero / inventing a value).
    """
    total = 0.0
    errors_5xx = 0.0
    for metric in REQUEST_COUNTER.collect():
        for sample in metric.samples:
            if not sample.name.endswith("_total"):
                continue
            labels = sample.labels
            if labels.get("service") != _API_GATEWAY_SERVICE:
                continue
            count = sample.value
            total += count
            status_code = labels.get("status_code", "")
            if status_code.startswith("5"):
                errors_5xx += count
    if total <= 0:
        return None
    return (total - errors_5xx) / total


def _observed_for(service_name: str, slo: dict[str, Any]) -> SLOObserved:
    """Build the honest observed block for one SLO.

    Real value only for api-gateway availability/error_rate (process-lifetime sample); every
    other SLO is flagged ``data_available: false`` — no fabrication (CLAUDE.md §3.6).
    """
    slo_name = str(slo.get("name", ""))
    if service_name == _API_GATEWAY_SERVICE and slo_name in _OBSERVABLE_API_SLOS:
        ratio = _api_gateway_non5xx_ratio()
        if ratio is None:
            return SLOObserved(
                data_available=False,
                note=(
                    "No requests recorded by the in-process http_requests_total counter yet; "
                    "no observed value to report."
                ),
            )
        return SLOObserved(
            data_available=True,
            value=round(ratio * 100, 4),
            unit="percent",
            source="prometheus:http_requests_total (in-process)",
            scope="process_lifetime",
            note=(
                "Process-lifetime sample (share of non-5xx api-gateway responses since this "
                "process started). NOT the 30-day SLO-window compliance figure — computing that "
                "requires a metrics-query (PromQL) layer the service does not yet have."
            ),
        )

    return SLOObserved(
        data_available=False,
        note=(
            "Live value requires a metrics-query (PromQL) layer to evaluate this SLI over its "
            "window; not computable in-process. Target shown is from docs/sre/slo/slo.yaml."
        ),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/slo-status",
    response_model=SLOStatusResponse,
    summary="SLO targets and honest observed status",
)
async def get_slo_status(
    _principal: Principal = Depends(get_principal),
) -> SLOStatusResponse:
    """Return every SLO defined in docs/sre/slo/slo.yaml with an honest ``observed`` block.

    Requires a valid bearer JWT (read access). The ``target``/``target_ms``/``target_max`` and
    ``window`` are the real configured SLO definitions. ``observed.data_available`` is True only
    where a real in-process sample exists (api-gateway availability/error-rate, scoped as a
    process-lifetime sample); everywhere else it is False with a ``note`` — no observed number is
    ever fabricated (CLAUDE.md §3.6, SPEC-API-004).
    """
    data = load_slo_definitions()
    services: list[SLOServiceStatus] = []

    for svc in data.get("services", []) or []:
        svc_name = str(svc.get("name", ""))
        items: list[SLOItemStatus] = []
        for slo in svc.get("slos", []) or []:
            items.append(
                SLOItemStatus(
                    name=str(slo.get("name", "")),
                    sli_type=str(slo.get("sli_type", "")),
                    description=slo.get("description"),
                    target=slo.get("target"),
                    target_ms=slo.get("target_ms"),
                    target_max=slo.get("target_max"),
                    window=slo.get("window"),
                    observed=_observed_for(svc_name, slo),
                )
            )
        services.append(
            SLOServiceStatus(
                name=svc_name,
                description=svc.get("description"),
                slos=items,
            )
        )

    return SLOStatusResponse(
        source_version=str(data.get("version")) if data.get("version") is not None else None,
        generated_at=datetime.now(UTC),
        services=services,
    )
