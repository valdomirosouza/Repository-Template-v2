package observability

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Business metrics for the event-worker. Registered to the default registry, so they are exposed by
// the existing promhttp handler on the metrics port — giving the event-consumer SLO a real emitter
// (W2-11). Names use the `event_worker_` prefix for clear ownership.
var (
	EventsProcessed = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "event_worker_events_processed_total",
		Help: "Total domain events processed, by event_type and outcome (success|error).",
	}, []string{"event_type", "outcome"})

	EventProcessingDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "event_worker_processing_duration_seconds",
		Help:    "End-to-end event processing duration in seconds, by event_type.",
		Buckets: prometheus.DefBuckets,
	}, []string{"event_type"})
)
