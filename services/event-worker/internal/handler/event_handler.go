package handler

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"

	"github.com/yourorg/monorepo/services/event-worker/internal/domain"
	"github.com/yourorg/monorepo/services/event-worker/internal/observability"
)

var tracer = otel.Tracer("event-worker/handler")

// Publisher sends processed events downstream.
type Publisher interface {
	Publish(ctx context.Context, event domain.ProcessedEvent) error
}

// EventHandler processes incoming domain events and publishes results.
type EventHandler struct {
	publisher Publisher
	workerID  string
	logger    *slog.Logger
}

func New(publisher Publisher, workerID string, logger *slog.Logger) *EventHandler {
	return &EventHandler{
		publisher: publisher,
		workerID:  workerID,
		logger:    logger,
	}
}

func (h *EventHandler) Handle(ctx context.Context, event domain.DomainEvent) (err error) {
	// W2-11: span (continues the producer's trace when the context carries one) + business metrics.
	ctx, span := tracer.Start(ctx, "event-worker.handle",
		trace.WithSpanKind(trace.SpanKindConsumer),
		trace.WithAttributes(
			attribute.String("event.entity_id", event.EntityID),
			attribute.String("event.type", string(event.EventType)),
			attribute.String("worker.id", h.workerID),
		),
	)
	start := time.Now()
	defer func() {
		observability.EventProcessingDuration.
			WithLabelValues(string(event.EventType)).
			Observe(time.Since(start).Seconds())
		outcome := "success"
		if err != nil {
			outcome = "error"
			span.RecordError(err)
			span.SetStatus(codes.Error, err.Error())
		}
		observability.EventsProcessed.WithLabelValues(string(event.EventType), outcome).Inc()
		span.End()
	}()

	h.logger.Info("handling event",
		slog.String("entity_id", event.EntityID),
		slog.String("event_type", string(event.EventType)),
	)

	if event.EntityID == "" {
		return fmt.Errorf("invalid event: missing entity_id")
	}

	processed := domain.ProcessedEvent{
		EntityID:    event.EntityID,
		EventType:   event.EventType,
		ProcessedAt: time.Now().UTC(),
		WorkerID:    h.workerID,
	}

	if err := h.publisher.Publish(ctx, processed); err != nil {
		return fmt.Errorf("publish processed event: %w", err)
	}

	h.logger.Info("event processed",
		slog.String("entity_id", event.EntityID),
		slog.String("worker_id", h.workerID),
	)
	return nil
}
