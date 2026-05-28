package handler

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/yourorg/monorepo/services/event-worker/internal/domain"
)

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

func (h *EventHandler) Handle(ctx context.Context, event domain.DomainEvent) error {
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
