package observability_test

import (
	"context"
	"testing"

	"github.com/prometheus/client_golang/prometheus"
	"go.opentelemetry.io/otel"

	"github.com/yourorg/monorepo/services/event-worker/internal/observability"
)

// W15-T5 (issue #392): metrics.go and tracing.go had no tests.

func TestInitTracer_EmptyEndpointIsNoOpButStillSetsPropagator(t *testing.T) {
	shutdown, err := observability.InitTracer(context.Background(), "", "event-worker", "test")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if err := shutdown(context.Background()); err != nil {
		t.Errorf("no-op shutdown must not error: %v", err)
	}
	fields := otel.GetTextMapPropagator().Fields()
	want := map[string]bool{"traceparent": false, "tracestate": false, "baggage": false}
	for _, f := range fields {
		if _, ok := want[f]; ok {
			want[f] = true
		}
	}
	for k, seen := range want {
		if !seen {
			t.Errorf("propagator field %q not installed (trace continuity across Kafka needs it)", k)
		}
	}
}

func TestBusinessMetrics_AreRegisteredWithOwnershipPrefix(t *testing.T) {
	observability.EventsProcessed.WithLabelValues("entity.created", "success").Inc()
	observability.EventProcessingDuration.WithLabelValues("entity.created").Observe(0.01)
	families, err := prometheus.DefaultGatherer.Gather()
	if err != nil {
		t.Fatalf("gather: %v", err)
	}
	seen := map[string]bool{}
	for _, f := range families {
		seen[f.GetName()] = true
	}
	for _, name := range []string{"event_worker_events_processed_total", "event_worker_processing_duration_seconds"} {
		if !seen[name] {
			t.Errorf("metric %q not registered on the default registry", name)
		}
	}
}
