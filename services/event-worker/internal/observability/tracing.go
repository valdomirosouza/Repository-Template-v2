// Package observability wires OpenTelemetry tracing and Prometheus business metrics for the
// event-worker, mirroring the Python reference instrumentation (src/observability/) so traces are
// continuous across the API → Kafka → worker boundary (W2-11).
package observability

import (
	"context"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

// InitTracer configures the global OTel tracer provider and the W3C propagator.
//
// The propagator is ALWAYS set so the worker extracts trace context from Kafka message headers when
// a producer injected it (trace continuity). If endpoint is empty, tracing is a no-op — the worker
// still runs and still exports Prometheus metrics. Returns a shutdown func to flush spans on exit.
func InitTracer(ctx context.Context, endpoint, serviceName, env string) (func(context.Context) error, error) {
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	if endpoint == "" {
		return func(context.Context) error { return nil }, nil
	}

	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(endpoint),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	res, err := resource.New(ctx, resource.WithAttributes(
		attribute.String("service.name", serviceName),
		attribute.String("deployment.environment", env),
	))
	if err != nil {
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tp)
	return tp.Shutdown, nil
}
