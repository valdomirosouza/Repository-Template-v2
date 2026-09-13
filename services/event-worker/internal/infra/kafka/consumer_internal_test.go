package kafka

import (
	"testing"

	"github.com/segmentio/kafka-go"

	"github.com/yourorg/monorepo/services/event-worker/internal/domain"
)

// W15-T5 (issue #392): the message-parsing and trace-carrier logic had no tests. These are
// in-package tests so the unexported helpers are covered without a broker.

func TestParseEvent_ValidMessage(t *testing.T) {
	msg := kafka.Message{Value: []byte(`{"entityId":"ent-00000000-0001","event":"entity.created","extra":1}`)}
	ev, err := parseEvent(msg)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ev.EntityID != "ent-00000000-0001" {
		t.Errorf("entity id: got %q", ev.EntityID)
	}
	if ev.EventType != domain.EventType("entity.created") {
		t.Errorf("event type: got %q", ev.EventType)
	}
	if ev.Payload != string(msg.Value) {
		t.Errorf("payload must carry the raw message")
	}
	if ev.ReceivedAt.IsZero() {
		t.Errorf("received_at must be set")
	}
}

func TestParseEvent_InvalidJSON(t *testing.T) {
	if _, err := parseEvent(kafka.Message{Value: []byte("{not json")}); err == nil {
		t.Fatal("expected an unmarshal error")
	}
}

func TestParseEvent_EmptyMessage(t *testing.T) {
	if _, err := parseEvent(kafka.Message{}); err == nil {
		t.Fatal("expected an error for an empty value")
	}
}

func TestKafkaHeaderCarrier_ExposesTraceHeaders(t *testing.T) {
	headers := []kafka.Header{
		{Key: "traceparent", Value: []byte("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01")},
		{Key: "baggage", Value: []byte("tenant=synthetic")},
	}
	carrier := kafkaHeaderCarrier(headers)
	if carrier.Get("traceparent") != "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01" {
		t.Errorf("traceparent not carried: %q", carrier.Get("traceparent"))
	}
	if got := len(carrier.Keys()); got != 2 {
		t.Errorf("expected 2 keys, got %d", got)
	}
	if kafkaHeaderCarrier(nil).Get("traceparent") != "" {
		t.Errorf("nil headers must yield an empty carrier")
	}
}

func TestNewProducer_ConfiguresWriterWithoutAutoCreate(t *testing.T) {
	p := NewProducer([]string{"broker-a:9092"}, "event.processed.v1")
	if p.writer.Topic != "event.processed.v1" {
		t.Errorf("topic: got %q", p.writer.Topic)
	}
	if p.writer.AllowAutoTopicCreation {
		t.Errorf("auto topic creation must stay disabled (topics are registered in services.yaml)")
	}
	if err := p.Close(); err != nil {
		t.Errorf("close: %v", err)
	}
}
