package kafka

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/segmentio/kafka-go"
	"github.com/yourorg/monorepo/services/event-worker/internal/domain"
)

type Producer struct {
	writer *kafka.Writer
}

func NewProducer(brokers []string, topic string) *Producer {
	return &Producer{
		writer: &kafka.Writer{
			Addr:                   kafka.TCP(brokers...),
			Topic:                  topic,
			AllowAutoTopicCreation: false,
			Balancer:               &kafka.LeastBytes{},
		},
	}
}

func (p *Producer) Publish(ctx context.Context, event domain.ProcessedEvent) error {
	payload, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}
	return p.writer.WriteMessages(ctx, kafka.Message{
		Key:   []byte(event.EntityID),
		Value: payload,
	})
}

func (p *Producer) Close() error {
	return p.writer.Close()
}
