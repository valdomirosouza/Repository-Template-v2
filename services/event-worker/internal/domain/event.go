package domain

import "time"

// EventType identifies the kind of domain event received.
type EventType string

const (
	EventTypeEntityCreated EventType = "entity.created"
	EventTypeEntityUpdated EventType = "entity.updated"
)

// DomainEvent is the normalised representation of an incoming Kafka message.
type DomainEvent struct {
	EntityID   string
	EventType  EventType
	Payload    string
	ReceivedAt time.Time
}

// ProcessedEvent is published to event.processed.v1 after successful handling.
type ProcessedEvent struct {
	EntityID    string
	EventType   EventType
	ProcessedAt time.Time
	WorkerID    string
}
