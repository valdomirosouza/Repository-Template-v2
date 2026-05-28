package handler_test

import (
	"context"
	"log/slog"
	"os"
	"testing"
	"time"

	"github.com/yourorg/monorepo/services/event-worker/internal/domain"
	"github.com/yourorg/monorepo/services/event-worker/internal/handler"
)

type mockPublisher struct {
	published []domain.ProcessedEvent
	err       error
}

func (m *mockPublisher) Publish(_ context.Context, event domain.ProcessedEvent) error {
	if m.err != nil {
		return m.err
	}
	m.published = append(m.published, event)
	return nil
}

func TestHandle_PublishesProcessedEvent(t *testing.T) {
	pub := &mockPublisher{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	h := handler.New(pub, "worker-1", logger)

	event := domain.DomainEvent{
		EntityID:   "entity-abc",
		EventType:  domain.EventTypeEntityCreated,
		Payload:    `{"name":"test"}`,
		ReceivedAt: time.Now(),
	}

	if err := h.Handle(context.Background(), event); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(pub.published) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(pub.published))
	}
	if pub.published[0].EntityID != "entity-abc" {
		t.Errorf("expected entity-abc, got %s", pub.published[0].EntityID)
	}
	if pub.published[0].WorkerID != "worker-1" {
		t.Errorf("expected worker-1, got %s", pub.published[0].WorkerID)
	}
}

func TestHandle_MissingEntityID_ReturnsError(t *testing.T) {
	pub := &mockPublisher{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	h := handler.New(pub, "worker-1", logger)

	event := domain.DomainEvent{EventType: domain.EventTypeEntityCreated}

	if err := h.Handle(context.Background(), event); err == nil {
		t.Fatal("expected error for missing entity_id, got nil")
	}
}

func TestHandle_PublisherError_Propagates(t *testing.T) {
	pub := &mockPublisher{err: context.DeadlineExceeded}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	h := handler.New(pub, "worker-1", logger)

	event := domain.DomainEvent{EntityID: "entity-xyz", EventType: domain.EventTypeEntityUpdated}

	if err := h.Handle(context.Background(), event); err == nil {
		t.Fatal("expected error from publisher, got nil")
	}
}
