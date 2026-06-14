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
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/yourorg/monorepo/services/event-worker/internal/config"
	"github.com/yourorg/monorepo/services/event-worker/internal/handler"
	"github.com/yourorg/monorepo/services/event-worker/internal/health"
	kafkainfra "github.com/yourorg/monorepo/services/event-worker/internal/infra/kafka"
	"github.com/yourorg/monorepo/services/event-worker/internal/observability"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	cfg := config.Load()

	// W2-11: OTel tracing (no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset). Flushed on shutdown.
	shutdownTracer, err := observability.InitTracer(
		context.Background(), cfg.OTLPEndpoint, cfg.ServiceName, cfg.AppEnv,
	)
	if err != nil {
		logger.Error("tracer init failed; continuing without tracing", slog.String("error", err.Error()))
	} else {
		defer func() { _ = shutdownTracer(context.Background()) }()
	}

	// Health server on dedicated port — serves /healthz (liveness) and /readyz (readiness).
	// Starts before Kafka so the startupProbe can verify the process is alive immediately.
	// SetReady(true) is called after the Kafka consumer group join completes. (specs/k8s/probe-strategy.md §3.3)
	healthSrv := health.New()
	healthSrv.Start(cfg.HealthPort)
	logger.Info("health server listening", slog.Int("port", cfg.HealthPort))

	brokers := strings.Split(cfg.KafkaBootstrapServers, ",")
	topics := []string{cfg.KafkaTopicInput1, cfg.KafkaTopicInput2}

	producer := kafkainfra.NewProducer(brokers, cfg.KafkaTopicOutput)
	defer producer.Close() //nolint:errcheck

	workerID, _ := os.Hostname()
	h := handler.New(producer, workerID, logger)

	consumer := kafkainfra.NewConsumer(brokers, topics, cfg.KafkaConsumerGroup, h, logger)
	defer consumer.Close() //nolint:errcheck

	// Prometheus metrics + legacy /health endpoint (kept for backward compat with non-K8s scrapers)
	go func() {
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())
		mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusOK)
		})
		addr := fmt.Sprintf(":%d", cfg.PrometheusPort)
		logger.Info("metrics server listening", slog.String("addr", addr))
		srv := &http.Server{Addr: addr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}
		if err := srv.ListenAndServe(); err != nil {
			logger.Error("metrics server failed", slog.String("error", err.Error()))
		}
	}()

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	logger.Info("event-worker started",
		slog.String("topics", strings.Join(topics, ",")),
		slog.String("group", cfg.KafkaConsumerGroup),
	)

	// Signal readiness after the Kafka consumer group has joined and received partition assignment.
	healthSrv.SetReady(true)
	logger.Info("event-worker ready — Kafka consumer group joined")

	if err := consumer.Run(ctx); err != nil {
		logger.Error("consumer exited with error", slog.String("error", err.Error()))
		os.Exit(1)
	}
	logger.Info("event-worker stopped gracefully")
}
