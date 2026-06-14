package handler_test

import (
	"context"
	"errors"
	"log/slog"
	"os"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus/testutil"

	"github.com/yourorg/monorepo/services/event-worker/internal/domain"
	"github.com/yourorg/monorepo/services/event-worker/internal/handler"
	"github.com/yourorg/monorepo/services/event-worker/internal/observability"
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

func TestHandle_RecordsSuccessMetric(t *testing.T) {
	pub := &mockPublisher{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	h := handler.New(pub, "worker-1", logger)
	et := string(domain.EventTypeEntityCreated)

	before := testutil.ToFloat64(observability.EventsProcessed.WithLabelValues(et, "success"))
	event := domain.DomainEvent{EntityID: "e-metric-ok", EventType: domain.EventTypeEntityCreated}
	if err := h.Handle(context.Background(), event); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	after := testutil.ToFloat64(observability.EventsProcessed.WithLabelValues(et, "success"))
	if after != before+1 {
		t.Errorf("events_processed_total{success} = %v, want %v", after, before+1)
	}
}

func TestHandle_RecordsErrorMetric(t *testing.T) {
	pub := &mockPublisher{err: errors.New("publish failed")}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	h := handler.New(pub, "worker-1", logger)
	et := string(domain.EventTypeEntityCreated)

	before := testutil.ToFloat64(observability.EventsProcessed.WithLabelValues(et, "error"))
	event := domain.DomainEvent{EntityID: "e-metric-err", EventType: domain.EventTypeEntityCreated}
	if err := h.Handle(context.Background(), event); err == nil {
		t.Fatal("expected an error")
	}
	after := testutil.ToFloat64(observability.EventsProcessed.WithLabelValues(et, "error"))
	if after != before+1 {
		t.Errorf("events_processed_total{error} = %v, want %v", after, before+1)
	}
}
