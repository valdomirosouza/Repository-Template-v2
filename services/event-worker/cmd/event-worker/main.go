package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/yourorg/monorepo/services/event-worker/internal/config"
	"github.com/yourorg/monorepo/services/event-worker/internal/handler"
	kafkainfra "github.com/yourorg/monorepo/services/event-worker/internal/infra/kafka"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	cfg := config.Load()

	brokers := strings.Split(cfg.KafkaBootstrapServers, ",")
	topics := []string{cfg.KafkaTopicInput1, cfg.KafkaTopicInput2}

	producer := kafkainfra.NewProducer(brokers, cfg.KafkaTopicOutput)
	defer producer.Close() //nolint:errcheck

	workerID, _ := os.Hostname()
	h := handler.New(producer, workerID, logger)

	consumer := kafkainfra.NewConsumer(brokers, topics, cfg.KafkaConsumerGroup, h, logger)
	defer consumer.Close() //nolint:errcheck

	// Prometheus metrics endpoint
	go func() {
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())
		mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusOK)
		})
		addr := fmt.Sprintf(":%d", cfg.PrometheusPort)
		logger.Info("metrics server listening", slog.String("addr", addr))
		if err := http.ListenAndServe(addr, mux); err != nil {
			logger.Error("metrics server failed", slog.String("error", err.Error()))
		}
	}()

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	logger.Info("event-worker started",
		slog.String("topics", strings.Join(topics, ",")),
		slog.String("group", cfg.KafkaConsumerGroup),
	)

	if err := consumer.Run(ctx); err != nil {
		logger.Error("consumer exited with error", slog.String("error", err.Error()))
		os.Exit(1)
	}
	logger.Info("event-worker stopped gracefully")
}
