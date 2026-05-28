package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/segmentio/kafka-go"
	"github.com/yourorg/monorepo/services/event-worker/internal/domain"
	"github.com/yourorg/monorepo/services/event-worker/internal/handler"
)

type Consumer struct {
	reader  *kafka.Reader
	handler *handler.EventHandler
	logger  *slog.Logger
}

func NewConsumer(brokers []string, topics []string, groupID string, h *handler.EventHandler, logger *slog.Logger) *Consumer {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        brokers,
		GroupTopics:    topics,
		GroupID:        groupID,
		MinBytes:       1,
		MaxBytes:       10e6,
		CommitInterval: time.Second,
	})
	return &Consumer{reader: reader, handler: h, logger: logger}
}

func (c *Consumer) Run(ctx context.Context) error {
	c.logger.Info("kafka consumer started")
	for {
		msg, err := c.reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return nil // graceful shutdown
			}
			return fmt.Errorf("fetch message: %w", err)
		}

		event, err := parseEvent(msg)
		if err != nil {
			c.logger.Warn("skipping unparseable message", slog.String("error", err.Error()))
			if err := c.reader.CommitMessages(ctx, msg); err != nil {
				c.logger.Error("commit failed", slog.String("error", err.Error()))
			}
			continue
		}

		if err := c.handler.Handle(ctx, event); err != nil {
			c.logger.Error("handler error",
				slog.String("entity_id", event.EntityID),
				slog.String("error", err.Error()),
			)
		}

		if err := c.reader.CommitMessages(ctx, msg); err != nil {
			c.logger.Error("commit failed", slog.String("error", err.Error()))
		}
	}
}

func (c *Consumer) Close() error {
	return c.reader.Close()
}

type rawEvent struct {
	EntityID  string `json:"entityId"`
	EventType string `json:"event"`
}

func parseEvent(msg kafka.Message) (domain.DomainEvent, error) {
	var raw rawEvent
	if err := json.Unmarshal(msg.Value, &raw); err != nil {
		return domain.DomainEvent{}, fmt.Errorf("unmarshal: %w", err)
	}
	return domain.DomainEvent{
		EntityID:   raw.EntityID,
		EventType:  domain.EventType(raw.EventType),
		Payload:    string(msg.Value),
		ReceivedAt: time.Now().UTC(),
	}, nil
}
