package config

import (
	"os"
	"strconv"
)

type Config struct {
	KafkaBootstrapServers string
	KafkaConsumerGroup    string
	KafkaTopicInput1      string
	KafkaTopicInput2      string
	KafkaTopicOutput      string
	PrometheusPort        int
	AppEnv                string
}

func Load() Config {
	return Config{
		KafkaBootstrapServers: getEnv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
		KafkaConsumerGroup:    getEnv("KAFKA_CONSUMER_GROUP", "event-worker-group"),
		KafkaTopicInput1:      getEnv("KAFKA_TOPIC_ENTITY_CREATED", "domain.entity.created.v1"),
		KafkaTopicInput2:      getEnv("KAFKA_TOPIC_ENTITY_UPDATED", "domain.entity.updated.v1"),
		KafkaTopicOutput:      getEnv("KAFKA_TOPIC_EVENT_PROCESSED", "event.processed.v1"),
		PrometheusPort:        getEnvInt("PROMETHEUS_PORT", 9091),
		AppEnv:                getEnv("APP_ENV", "development"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}
