"""Unit tests for src/observability/otel_setup.py and dora_metrics.py (W15-T1, issue #388).

Spec: specs/system/architecture.md (Observability) · specs/observability/dora-metrics.md
ADR:  ADR-0004, ADR-0028

Both modules had zero referencing tests. The OTel bootstrap is exercised with the OTLP
exporters replaced by fakes so nothing touches the network; the global providers are restored
after each test so the rest of the suite is unaffected.
"""

from __future__ import annotations

from typing import Any

import pytest
from opentelemetry import metrics, propagate, trace
from opentelemetry.util._once import Once
from prometheus_client import REGISTRY

import src.observability.otel_setup as otel_setup
from src.observability import dora_metrics
from src.shared.config import settings

pytestmark = [pytest.mark.unit, pytest.mark.requirement("SPEC-OBS-003")]


class _FakeExporter:
    instances: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        _FakeExporter.instances.append(kwargs)

    def export(self, *a: Any, **k: Any) -> Any:  # pragma: no cover - never called
        return None

    def shutdown(self, *a: Any, **k: Any) -> None:
        return None

    def force_flush(self, *a: Any, **k: Any) -> bool:
        return True

    @property
    def _preferred_temporality(self) -> dict[Any, Any]:  # PeriodicExportingMetricReader reads it
        return {}

    @property
    def _preferred_aggregation(self) -> dict[Any, Any]:
        return {}


@pytest.fixture
def isolated_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake exporters, reset the module singletons, and restore global providers afterwards."""
    _FakeExporter.instances = []
    monkeypatch.setattr(otel_setup, "OTLPSpanExporter", _FakeExporter)
    monkeypatch.setattr(otel_setup, "OTLPMetricExporter", _FakeExporter)
    monkeypatch.setattr(otel_setup, "_tracer_provider", None)
    monkeypatch.setattr(otel_setup, "_meter_provider", None)
    monkeypatch.setattr(otel_setup.atexit, "register", lambda *a, **k: None)
    tp, mp, pr = (
        trace.get_tracer_provider(),
        metrics.get_meter_provider(),
        propagate.get_global_textmap(),
    )
    # The OTel globals are set-once; reach into the API's internals to reset them for the test.
    monkeypatch.setattr(trace, "_TRACER_PROVIDER", None, raising=False)
    monkeypatch.setattr(trace, "_TRACER_PROVIDER_SET_ONCE", Once(), raising=False)
    monkeypatch.setattr(metrics, "_METER_PROVIDER", None, raising=False)
    monkeypatch.setattr(metrics, "_METER_PROVIDER_SET_ONCE", Once(), raising=False)
    yield
    propagate.set_global_textmap(pr)
    monkeypatch.setattr(trace, "_TRACER_PROVIDER", tp, raising=False)
    monkeypatch.setattr(metrics, "_METER_PROVIDER", mp, raising=False)


def test_setup_installs_providers_with_resource_and_endpoint(isolated_otel: None):
    otel_setup.setup_telemetry(service_name="svc-under-test", service_version="9.9.9")
    provider = trace.get_tracer_provider()
    assert isinstance(provider, otel_setup.TracerProvider)
    attrs = provider.resource.attributes
    assert attrs["service.name"] == "svc-under-test" and attrs["service.version"] == "9.9.9"
    assert attrs["deployment.environment"] == settings.app_env
    # both exporters built against the configured endpoint, insecure outside production
    assert {e["endpoint"] for e in _FakeExporter.instances} == {
        settings.otel_exporter_otlp_endpoint
    }
    assert all(e["insecure"] is (settings.app_env != "production") for e in _FakeExporter.instances)
    assert isinstance(metrics.get_meter_provider(), otel_setup.MeterProvider)


def test_setup_is_idempotent(isolated_otel: None):
    otel_setup.setup_telemetry(service_name="first")
    first = trace.get_tracer_provider()
    otel_setup.setup_telemetry(service_name="second")  # no-op
    assert trace.get_tracer_provider() is first
    assert len(_FakeExporter.instances) == 2  # one span + one metric exporter, not four


def test_setup_installs_w3c_and_baggage_propagators(isolated_otel: None):
    otel_setup.setup_telemetry(service_name="svc")
    carrier: dict[str, str] = {}
    with trace.get_tracer_provider().get_tracer("t").start_as_current_span("s"):
        propagate.inject(carrier)
    assert "traceparent" in carrier  # TraceContext propagator active
    fields = propagate.get_global_textmap().fields
    assert {"traceparent", "tracestate", "baggage"} <= set(fields)


def test_shutdown_is_safe_when_never_initialised(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(otel_setup, "_tracer_provider", None)
    monkeypatch.setattr(otel_setup, "_meter_provider", None)
    assert otel_setup._shutdown_telemetry() is None  # must not raise
    assert otel_setup._tracer_provider is None and otel_setup._meter_provider is None


# ── DORA metrics ───────────────────────────────────────────────────────────────


def test_dora_metrics_are_registered_with_spec_names_and_labels():
    names = {
        "dora_deployments": dora_metrics.dora_deployments_total,
        "dora_lead_time_seconds": dora_metrics.dora_lead_time_seconds,
        "dora_change_failure_rate": dora_metrics.dora_change_failure_rate,
        "dora_mttr_seconds": dora_metrics.dora_mttr_seconds,
    }
    registered = {m.name for m in REGISTRY.collect()}
    assert set(names) <= registered
    assert dora_metrics.dora_deployments_total._labelnames == ("service", "environment", "outcome")
    assert dora_metrics.dora_lead_time_seconds._labelnames == ("service",)


def test_dora_metrics_record_values():
    dora_metrics.dora_deployments_total.labels("svc", "staging", "success").inc()
    dora_metrics.dora_lead_time_seconds.labels("svc").observe(7_200)
    dora_metrics.dora_change_failure_rate.labels("svc").set(0.04)
    dora_metrics.dora_mttr_seconds.labels("svc").observe(600)
    assert dora_metrics.dora_deployments_total.labels("svc", "staging", "success")._value.get() >= 1
    assert dora_metrics.dora_change_failure_rate.labels("svc")._value.get() == 0.04
    # histogram buckets are the spec's SLO edges (1h…48h lead time; 10min…4h MTTR)
    assert dora_metrics.dora_lead_time_seconds._upper_bounds[:2] == [3_600, 7_200]
    assert dora_metrics.dora_mttr_seconds._upper_bounds[0] == 600
