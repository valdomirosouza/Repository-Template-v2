# Quickstart — Go Backend

> **Stack:** Go 1.23 · net/http (or chi) · pgx · confluent-kafka-go · OpenTelemetry Go SDK
> **Service types:** High-throughput worker, sidecar, Kafka consumer, gRPC server
> **Read first:** [docs/quickstart/README.md](README.md) for shared governance rules.

---

## Prerequisites

| Tool             | Version | Install                                                          |
| ---------------- | ------- | ---------------------------------------------------------------- |
| Go               | 1.23+   | [go.dev/dl](https://go.dev/dl/) or `brew install go`             |
| Docker & Compose | 24+     | [docker.com](https://www.docker.com/products/docker-desktop/)    |
| make             | any     | pre-installed on macOS/Linux                                     |
| kubectl          | 1.28+   | `brew install kubectl`                                           |
| helm             | 3.x     | `brew install helm`                                              |
| protoc           | 3.x     | `brew install protobuf`                                          |
| protoc-gen-go    | latest  | `go install google.golang.org/protobuf/cmd/protoc-gen-go@latest` |

---

## Which files are yours

```
services/<your-service>/
├── cmd/<your-service>/
│   └── main.go          ← entry point only — wire dependencies here
├── internal/
│   ├── handler/         ← HTTP/gRPC handlers (thin — delegate to domain)
│   ├── domain/          ← business logic, pure functions, no I/O
│   ├── infra/           ← adapters: pgx queries, Kafka producer/consumer
│   └── config/          ← env-based config with envconfig or viper
├── api/                 ← generated gRPC stubs (do not hand-write)
└── Makefile             ← service-level make targets
```

**Files you do NOT own (shared contracts — read-only):**

```
docs/api/openapi/       ← REST contract — generate stubs if needed
docs/api/asyncapi/      ← Kafka contract — defines topics and schemas
docs/api/grpc/proto/    ← gRPC definitions — run protoc to regenerate api/
infrastructure/message-broker/schema-registry/avro/  ← Avro schemas (use goavro)
```

---

## Setup

```bash
# 1. Install Go dependencies
go mod download

# 2. Generate gRPC stubs from shared proto files
make gen-proto-go

# 3. Copy and configure environment
cp .env.example .env
# Required fields — edit before running:
#   DATABASE_URL  postgres://user:password@localhost:5432/dbname?sslmode=disable
#   REDIS_URL     redis://localhost:6379/0
#   SECRET_KEY    minimum-32-character-secret

# 4. Start shared infrastructure
docker compose up -d

# 5. Confirm baseline is green
make test-go
make lint-go
```

Expected output: all tests pass, no lint violations.

---

## Daily workflow

```bash
make test-go          # unit + integration tests with coverage
make test-unit-go     # unit only (fast, no Docker required)
make lint-go          # golangci-lint (staticcheck, errcheck, gosec)
make format-go        # gofmt + goimports
make run-go           # start service (air for hot-reload)
```

---

## Key architectural patterns

### Config — never hardcode values

All configuration comes from environment variables:

```go
package config

import "github.com/kelseyhightower/envconfig"

type Config struct {
    DatabaseURL        string `envconfig:"DATABASE_URL" required:"true"`
    RedisURL           string `envconfig:"REDIS_URL" required:"true"`
    HITLRiskThreshold  float64 `envconfig:"HITL_RISK_THRESHOLD" default:"0.7"`
    LLMTimeoutSeconds  int    `envconfig:"LLM_CALL_TIMEOUT_SECONDS" default:"30"`
}

func Load() (*Config, error) {
    var cfg Config
    return &cfg, envconfig.Process("", &cfg)
}
```

Never use `os.Getenv()` directly in service code.

### Resilience — context timeouts + retry + circuit breaker

```go
import (
    "github.com/sony/gobreaker"
    "golang.org/x/time/rate"
)

// Every external call gets a deadline
ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
defer cancel()

// Wrap with circuit breaker
cb := gobreaker.NewCircuitBreaker(gobreaker.Settings{
    Name:        "llm-client",
    MaxRequests: 3,
    Interval:    10 * time.Second,
    Timeout:     60 * time.Second,
})

result, err := cb.Execute(func() (interface{}, error) {
    return llmClient.Complete(ctx, prompt)
})
```

Always propagate context — never drop it.

### PII — mask before everything

```go
import "github.com/yourorg/shared/guardrails"

// Before any log write, external call, or Kafka publish:
safePayload, err := guardrails.MaskJSON(rawPayload)
if err != nil {
    return fmt.Errorf("pii masking failed: %w", err)
}
slog.InfoContext(ctx, "processing request", "payload", safePayload)
```

See `docs/privacy/pii-inventory.md` for PII classification levels (L1–L4).

### Agent actions — always route through HITL REST API

Go services call the HITL gateway via HTTP (the gateway runs in the Python service):

```go
type HITLClient struct {
    baseURL    string
    httpClient *http.Client
}

func (c *HITLClient) SubmitForApproval(ctx context.Context, req HITLRequest) (*HITLResponse, error) {
    body, _ := json.Marshal(req)
    httpReq, _ := http.NewRequestWithContext(ctx, http.MethodPost,
        c.baseURL+"/v1/hitl/requests", bytes.NewReader(body))
    httpReq.Header.Set("Content-Type", "application/json")

    resp, err := c.httpClient.Do(httpReq)
    // handle response...
}
```

Full spec: `docs/api/openapi/v1/openapi.yaml` — `/v1/hitl` paths.

### Kafka — use generated consumer patterns

```go
// Topic names come from services.yaml via config — never hardcode
consumer, err := kafka.NewConsumer(&kafka.ConfigMap{
    "bootstrap.servers": cfg.KafkaBrokers,
    "group.id":          "my-service-consumer-group",
    "auto.offset.reset": "earliest",
})

consumer.SubscribeTopics([]string{cfg.Topics.RequestCreated}, nil)

for {
    msg, err := consumer.ReadMessage(ctx)
    if err != nil {
        // handle error, respect ctx.Done()
        continue
    }
    // process message — validate Avro schema before use
}
```

### Structured logging

```go
import "log/slog"

// OTel trace_id is injected automatically via slog handler bridge
slog.InfoContext(ctx, "processing item",
    slog.String("item_id", itemID),
    slog.String("action", "process"),
)

// Never use fmt.Println or log.Printf
```

---

## Observability

Instrument with the OpenTelemetry Go SDK — traces propagate automatically via context:

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/metric"
)

var tracer = otel.Tracer("my-service")
var meter = otel.Meter("my-service")

// In your handler:
ctx, span := tracer.Start(ctx, "process-item")
defer span.End()

// Golden Signal counter:
requestsTotal, _ := meter.Int64Counter("requests_total",
    metric.WithDescription("Total HTTP requests"))
requestsTotal.Add(ctx, 1,
    metric.WithAttributes(
        attribute.String("method", r.Method),
        attribute.Int("status_code", statusCode),
    ))
```

Expose metrics on `:8080/metrics` — the Prometheus scraper will pick them up.

---

## Testing conventions

```go
// Unit test — pure functions, no I/O
func TestProcessItem(t *testing.T) {
    result, err := domain.ProcessItem(input)
    require.NoError(t, err)
    assert.Equal(t, expected, result)
}

// Integration test — testcontainers-go with real PostgreSQL + Kafka
func TestConsumer_Integration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test")
    }
    ctx := context.Background()
    pgContainer, _ := postgres.RunContainer(ctx,
        testcontainers.WithImage("postgres:16"),
    )
    defer pgContainer.Terminate(ctx)
    // wire up and test
}
```

Run unit tests only: `go test -short ./...`
Coverage must be ≥ 80% before merge. CI enforces this via `go test -coverprofile`.

---

## Deployment

```bash
# Build image
make build-go SERVICE=<your-service>

# Deploy to staging
make deploy-staging SERVICE=<your-service>

# Check health (Go services expose /health and /ready)
curl http://staging.internal/<your-service>/health
curl http://staging.internal/<your-service>/ready
```

K8s manifests: `infrastructure/k8s/` — do not modify `deployment.yaml` probe configuration
without reviewing `docs/runbooks/RB-003-hitl-recovery.md`.

---

## Key ADRs for Go developers

| ADR                                                       | Why it matters to you                        |
| --------------------------------------------------------- | -------------------------------------------- |
| [ADR-0002](../adr/ADR-0002-technology-stack-selection.md) | Go rationale — when Go is preferred          |
| [ADR-0003](../adr/ADR-0003-async-api-strategy.md)         | When to use Kafka vs REST vs gRPC            |
| [ADR-0005](../adr/ADR-0005-message-broker-selection.md)   | Kafka configuration and consumer group rules |
| [ADR-0007](../adr/ADR-0007-service-mesh.md)               | mTLS, sidecar proxy, traffic policies        |
| [ADR-0011](../adr/ADR-0011-hitl-hotl-model.md)            | HITL REST API integration from Go services   |
