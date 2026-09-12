package config_test

import (
	"testing"

	"github.com/yourorg/monorepo/services/event-worker/internal/config"
)

// W15-T5 (issue #392): config.go had no tests despite the 80 % gate.

func TestLoad_Defaults(t *testing.T) {
	t.Setenv("KAFKA_BOOTSTRAP_SERVERS", "")
	t.Setenv("PROMETHEUS_PORT", "")
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
	cfg := config.Load()
	if cfg.KafkaBootstrapServers != "localhost:9092" {
		t.Errorf("bootstrap default: got %q", cfg.KafkaBootstrapServers)
	}
	if cfg.KafkaTopicInput1 != "domain.entity.created.v1" || cfg.KafkaTopicInput2 != "domain.entity.updated.v1" {
		t.Errorf("input topics default: got %q / %q", cfg.KafkaTopicInput1, cfg.KafkaTopicInput2)
	}
	if cfg.KafkaTopicOutput != "event.processed.v1" {
		t.Errorf("output topic default: got %q", cfg.KafkaTopicOutput)
	}
	if cfg.PrometheusPort != 9091 || cfg.HealthPort != 8081 {
		t.Errorf("port defaults: got %d / %d", cfg.PrometheusPort, cfg.HealthPort)
	}
	if cfg.OTLPEndpoint != "" {
		t.Errorf("tracing must be disabled by default, got endpoint %q", cfg.OTLPEndpoint)
	}
	if cfg.ServiceName != "event-worker" || cfg.AppEnv != "development" {
		t.Errorf("identity defaults: %q / %q", cfg.ServiceName, cfg.AppEnv)
	}
}

func TestLoad_EnvOverrides(t *testing.T) {
	t.Setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-a:9092,kafka-b:9092")
	t.Setenv("KAFKA_TOPIC_EVENT_PROCESSED", "event.processed.v2")
	t.Setenv("PROMETHEUS_PORT", "9999")
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "otel:4317")
	cfg := config.Load()
	if cfg.KafkaBootstrapServers != "kafka-a:9092,kafka-b:9092" {
		t.Errorf("bootstrap override: got %q", cfg.KafkaBootstrapServers)
	}
	if cfg.KafkaTopicOutput != "event.processed.v2" {
		t.Errorf("topic override: got %q", cfg.KafkaTopicOutput)
	}
	if cfg.PrometheusPort != 9999 {
		t.Errorf("port override: got %d", cfg.PrometheusPort)
	}
	if cfg.OTLPEndpoint != "otel:4317" {
		t.Errorf("otlp override: got %q", cfg.OTLPEndpoint)
	}
}

func TestLoad_InvalidIntFallsBackToDefault(t *testing.T) {
	t.Setenv("PROMETHEUS_PORT", "not-a-number")
	if cfg := config.Load(); cfg.PrometheusPort != 9091 {
		t.Errorf("invalid int must fall back to default, got %d", cfg.PrometheusPort)
	}
}
