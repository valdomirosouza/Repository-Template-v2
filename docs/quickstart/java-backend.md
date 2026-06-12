# Quickstart — Java Backend

> **Stack:** Java 21 · Spring Boot 3 · Spring Data JPA · Spring Kafka · Micrometer · OpenTelemetry Java Agent
> **Service types:** Domain REST API, event-driven domain service, gRPC server
> **Read first:** [docs/quickstart/README.md](README.md) for shared governance rules.

---

## Prerequisites

| Tool             | Version | Install                                                            |
| ---------------- | ------- | ------------------------------------------------------------------ |
| Java (JDK)       | 21+     | `brew install temurin@21` or [adoptium.net](https://adoptium.net/) |
| Maven            | 3.9+    | `brew install maven`                                               |
| Docker & Compose | 24+     | [docker.com](https://www.docker.com/products/docker-desktop/)      |
| make             | any     | pre-installed on macOS/Linux                                       |
| kubectl          | 1.28+   | `brew install kubectl`                                             |
| helm             | 3.x     | `brew install helm`                                                |

---

## Which files are yours

```
services/<your-service>/
├── src/main/java/com/yourorg/<service>/
│   ├── api/           ← REST controllers (generated stubs from OpenAPI)
│   ├── domain/        ← business logic, domain models, ports
│   ├── infra/         ← adapters: JPA repos, Kafka producers/consumers
│   └── config/        ← Spring config classes, beans
├── src/main/resources/
│   └── application.yml
└── src/test/
    ├── unit/          ← @SpringBootTest slices, Mockito mocks
    └── integration/   ← Testcontainers with real PostgreSQL + Kafka
```

**Files you do NOT own (shared contracts — read-only):**

```
docs/api/openapi/       ← REST contract — generate stubs with openapi-generator-maven-plugin
docs/api/asyncapi/      ← Kafka contract — generate consumers with asyncapi-generator
docs/api/grpc/proto/    ← gRPC definitions — generate with protoc-gen-grpc-java
infrastructure/message-broker/schema-registry/avro/  ← generate with avro-maven-plugin
```

---

## Setup

```bash
# 1. Start shared infrastructure
docker compose up -d

# 2. Copy and configure environment
cp .env.example .env
# Required fields — edit before running:
#   DATABASE_URL      jdbc:postgresql://localhost:5432/dbname
#   SPRING_DATASOURCE_USERNAME  your-db-user
#   SPRING_DATASOURCE_PASSWORD  your-db-password
#   ANTHROPIC_API_KEY           (only if service calls LLM directly)
#   SECRET_KEY                  minimum-32-character-secret

# 3. Generate API stubs from shared contracts
mvn generate-sources -pl services/<your-service>

# 4. Build and run tests
make test-java SERVICE=<your-service>

# 5. Run the service
make run-java SERVICE=<your-service>
```

Expected output: all tests pass, no lint violations.

---

## Daily workflow

```bash
make test-java SERVICE=<svc>       # unit + integration tests with coverage
make test-unit-java SERVICE=<svc>  # unit only (fast, no Docker required)
make lint-java SERVICE=<svc>       # checkstyle + SpotBugs (fast, no network)
make lint-java-sca SERVICE=<svc>   # OWASP dependency-check only (slow — downloads NVD; CI runs this)
make format-java SERVICE=<svc>     # google-java-format
make run-java SERVICE=<svc>        # start Spring Boot dev server
```

---

## Key architectural patterns

### Config — never hardcode values

All configuration comes from `application.yml` backed by environment variables:

```yaml
# application.yml
app:
  llm-timeout-seconds: ${LLM_CALL_TIMEOUT_SECONDS:30}
  hitl:
    risk-threshold: ${HITL_RISK_THRESHOLD:0.7}
    max-pending: ${HITL_MAX_PENDING_REQUESTS:100}
```

```java
@ConfigurationProperties(prefix = "app")
@Validated
public record AppProperties(
    @Positive int llmTimeoutSeconds,
    HitlProperties hitl
) {}
```

Never use `System.getenv()` directly in service code.

### Resilience — use Spring Retry + Resilience4j

```java
@Service
public class ExternalCallService {

    private final CircuitBreaker circuitBreaker;

    @Retry(name = "llm-client", fallbackMethod = "fallback")
    @CircuitBreaker(name = "llm-client")
    public CompletableFuture<String> callLLM(String prompt) {
        // External LLM call
    }

    private CompletableFuture<String> fallback(String prompt, Exception ex) {
        // Return safe degraded response
    }
}
```

Configure circuit breakers in `application.yml` under `resilience4j.circuitbreaker`.

### PII — mask before everything

```java
import com.yourorg.shared.guardrails.PiiMasker;

// Before any log write, LLM call, or Kafka publish:
String safePayload = piiMasker.maskJson(rawPayload);
log.info("Processing request payload={}", safePayload);
```

See `docs/privacy/pii-inventory.md` for PII classification levels (L1–L4).

### Agent actions — always route through HITL REST API

Java services call the HITL gateway via its REST API (the HITL gateway runs in the Python service):

```java
@Service
public class HitlClient {

    private final WebClient webClient;

    public Mono<HitlResponse> submitForApproval(HitlRequest request) {
        return webClient.post()
            .uri("/v1/hitl/requests")
            .bodyValue(request)
            .retrieve()
            .bodyToMono(HitlResponse.class);
    }

    public Mono<HitlDecision> pollDecision(String requestId) {
        return webClient.get()
            .uri("/v1/hitl/requests/{id}", requestId)
            .retrieve()
            .bodyToMono(HitlDecision.class);
    }
}
```

Full spec: `docs/api/openapi/v1/openapi.yaml` — `/v1/hitl` paths.

### Kafka — consume from generated stubs

```java
// Never write Kafka consumers by hand — generate from AsyncAPI spec:
// docs/api/asyncapi/v1/asyncapi.yaml

@Component
public class RequestCreatedConsumer {

    @KafkaListener(topics = "#{@kafkaTopics.requestCreated}")
    public void handle(
        @Payload RequestCreatedEvent event,
        @Header(KafkaHeaders.RECEIVED_TOPIC) String topic
    ) {
        // process event
    }
}
```

Topic names come from `services.yaml` via config — never hardcode strings.

### Structured logging

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import net.logstash.logback.argument.StructuredArguments;

private static final Logger log = LoggerFactory.getLogger(MyService.class);

// Always include trace_id (injected by OTel agent automatically):
log.info("Processing item {}",
    StructuredArguments.kv("item_id", itemId));
```

Never use `System.out.println()`.

---

## Observability

OTel Java Agent is attached via JVM args in the container. Micrometer exports Golden Signals automatically with Spring Boot Actuator:

```yaml
# application.yml
management:
  endpoints.web.exposure.include: health,ready,prometheus,info
  metrics.tags:
    service: ${spring.application.name}
    env: ${APP_ENV:development}
```

Add custom business metrics:

```java
@Autowired
MeterRegistry registry;

Counter.builder("agent.actions.total")
    .tag("action_type", actionType)
    .tag("outcome", outcome)
    .register(registry)
    .increment();
```

---

## Testing conventions

```java
// Unit test — mock all external dependencies
@ExtendWith(MockitoExtension.class)
class MyServiceTest {
    @Mock ExternalDep dep;
    @InjectMocks MyService sut;

    @Test
    void shouldProcessItem() { ... }
}

// Integration test — Testcontainers (real PostgreSQL + Kafka)
@SpringBootTest
@Testcontainers
class MyIntegrationTest {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", postgres::getJdbcUrl);
    }
}
```

Coverage must be ≥ 80% before merge. CI enforces this via JaCoCo.

---

## Deployment

```bash
# Build image
make build-java SERVICE=<your-service>

# Deploy to staging
make deploy-staging SERVICE=<your-service>

# Check health
curl http://staging.internal/<your-service>/actuator/health
curl http://staging.internal/<your-service>/actuator/health/readiness
```

K8s manifests: `infrastructure/k8s/` — do not modify `deployment.yaml` probe configuration
without reviewing `docs/runbooks/RB-003-hitl-recovery.md`.

---

## Key ADRs for Java developers

| ADR                                                       | Why it matters to you                            |
| --------------------------------------------------------- | ------------------------------------------------ |
| [ADR-0002](../adr/ADR-0002-technology-stack-selection.md) | Java/Spring Boot rationale and guidelines        |
| [ADR-0003](../adr/ADR-0003-async-api-strategy.md)         | When to use Kafka vs REST vs gRPC                |
| [ADR-0007](../adr/ADR-0007-service-mesh.md)               | mTLS, traffic policies, circuit breaking at mesh |
| [ADR-0011](../adr/ADR-0011-hitl-hotl-model.md)            | HITL REST API integration from Java services     |
| [ADR-0012](../adr/ADR-0012-pii-masking-strategy.md)       | PII masking requirements before log/LLM/Kafka    |
