# Contract-Driven Development

> **Read first:** [docs/quickstart/README.md](README.md) for shared governance rules.

This guide explains how to use the shared API contracts as the single source of truth and generate language-specific code from them. No stubs are written by hand.

---

## The Contract Hierarchy

```
docs/api/
├── openapi/v1/openapi.yaml      ← REST API contract (all services)
├── asyncapi/v1/asyncapi.yaml    ← Kafka event contract (all topics)
└── grpc/proto/ai_service.proto  ← gRPC contract (inter-service calls)

infrastructure/message-broker/schema-registry/avro/
└── *.avsc                       ← Avro schemas (Kafka payload shapes)
```

**Rule:** Every generated file is disposable. Never edit generated code — change the contract and regenerate.

---

## 1. REST — OpenAPI

### View the spec interactively

```bash
make openapi-ui   # opens Swagger UI on http://localhost:8082
```

### When to regenerate

Regenerate whenever `docs/api/openapi/v1/openapi.yaml` changes.

### Python (FastAPI)

FastAPI generates the OpenAPI spec _from_ the code — Python is the producer, not the consumer.

When another service publishes a spec that Python needs to consume, use `openapi-python-client`:

```bash
# Generate a typed async client
uv run openapi-python-client generate \
  --path docs/api/openapi/v1/openapi.yaml \
  --output-path src/shared/generated/rest_client
```

The generated client appears in `src/shared/generated/rest_client/`. Import it:

```python
from src.shared.generated.rest_client import Client
from src.shared.generated.rest_client.api.requests import create_request
from src.shared.generated.rest_client.models import CreateRequestBody

async with Client(base_url=settings.api_base_url) as client:
    response = await create_request.asyncio(client=client, body=CreateRequestBody(...))
```

### Java (Spring Boot)

Uses `openapi-generator-maven-plugin`. Add to your service's `pom.xml`:

```xml
<plugin>
  <groupId>org.openapitools</groupId>
  <artifactId>openapi-generator-maven-plugin</artifactId>
  <version>7.7.0</version>
  <executions>
    <execution>
      <goals><goal>generate</goal></goals>
      <configuration>
        <inputSpec>${project.basedir}/../../docs/api/openapi/v1/openapi.yaml</inputSpec>
        <generatorName>spring</generatorName>
        <apiPackage>com.yourorg.api.generated</apiPackage>
        <modelPackage>com.yourorg.model.generated</modelPackage>
        <configOptions>
          <interfaceOnly>true</interfaceOnly>
          <useSpringBoot3>true</useSpringBoot3>
          <useTags>true</useTags>
        </configOptions>
      </configuration>
    </execution>
  </executions>
</plugin>
```

```bash
make gen-sources-java SERVICE=domain-service  # runs mvn generate-sources
```

Implement the generated interface in your controller:

```java
@RestController
public class RequestsController implements RequestsApi {
    @Override
    public ResponseEntity<RequestResponse> createRequest(CreateRequestBody body) {
        // your implementation
    }
}
```

### TypeScript / Next.js

```bash
make gen-api-client-ts APP=frontend   # runs openapi-generator-cli
```

Generated client appears in `frontend/<app>/src/lib/api/`. Import:

```typescript
import { RequestsApi, Configuration } from "@/lib/api";

const api = new RequestsApi(
  new Configuration({ basePath: process.env.NEXT_PUBLIC_API_BASE_URL }),
);
const result = await api.createRequest({ createRequestBody: { prompt } });
```

### Go

Go services are typically consumers of other services, not of the main OpenAPI spec. Use `oapi-codegen` for REST clients:

```bash
go install github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@latest
oapi-codegen -package apiclient -generate types,client \
  docs/api/openapi/v1/openapi.yaml > services/event-worker/internal/apiclient/client.gen.go
```

Add to your service's `Makefile` target and commit the generated file to source control (Go convention).

---

## 2. Kafka Events — AsyncAPI

### View the spec interactively

```bash
make asyncapi-ui   # opens AsyncAPI Studio on http://localhost:8083
```

### When to regenerate

Regenerate whenever `docs/api/asyncapi/v1/asyncapi.yaml` changes.

### Adding a new topic

1. Add the channel and message definitions to `asyncapi.yaml`.
2. Add the Avro schema to `infrastructure/message-broker/schema-registry/avro/`.
3. Register the schema:

```bash
# Register schema with the local Schema Registry
curl -X POST http://localhost:8081/subjects/<topic-name>-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d "{\"schema\": $(jq -c . infrastructure/message-broker/schema-registry/avro/<schema>.avsc)}"
```

4. Add the topic to `services.yaml` under `topics:`.
5. Regenerate consumers in each language.

### Python (aiokafka)

```python
# src/agents/consumers/request_created.py
# Topic names come from settings — never hardcode strings
from src.shared.config import settings

async def consume_request_created(msg: bytes) -> None:
    # Deserialize with fastavro
    import io, fastavro
    schema = fastavro.parse_schema(load_avsc("request-created-v1.avsc"))
    record = fastavro.schemaless_reader(io.BytesIO(msg), schema)
    # process record...
```

### Java (Spring Kafka + Avro)

```java
// src/main/java/.../consumer/RequestCreatedConsumer.java
// The @KafkaListener topic value comes from @Value / config — never hardcoded.
@Component
public class RequestCreatedConsumer {

    @KafkaListener(topics = "#{@topics.requestCreated}")
    public void handle(@Payload RequestCreatedEvent event) {
        // Avro deserialization is handled by KafkaAvroDeserializer automatically
        // when spring.kafka.consumer.value-deserializer is configured
    }
}
```

`RequestCreatedEvent` is generated by `avro-maven-plugin` from the `.avsc` schema file.

### Go (confluent-kafka-go + goavro)

```go
// services/event-worker/internal/consumer/request_created.go
func (c *Consumer) processMessage(msg *kafka.Message) error {
    codec, _ := goavro.NewCodec(requestCreatedSchema)
    native, _, err := codec.NativeFromBinary(msg.Value)
    if err != nil {
        return fmt.Errorf("avro decode: %w", err)
    }
    record := native.(map[string]interface{})
    // process record...
}
```

---

## 3. gRPC — Protocol Buffers

### When to regenerate

Regenerate whenever any `.proto` file in `docs/api/grpc/proto/` changes.

### Python

```bash
# Add to pyproject.toml dev deps: grpcio-tools
uv run python -m grpc_tools.protoc \
  -I docs/api/grpc/proto \
  --python_out=src/shared/generated/grpc \
  --grpc_python_out=src/shared/generated/grpc \
  docs/api/grpc/proto/ai_service.proto
```

Usage:

```python
import grpc
from src.shared.generated.grpc import ai_service_pb2, ai_service_pb2_grpc

channel = grpc.aio.insecure_channel(settings.agent_grpc_address)
stub = ai_service_pb2_grpc.AgentServiceStub(channel)
response = await stub.SubmitTask(ai_service_pb2.SubmitTaskRequest(
    request_id=str(request_id),
    prompt=safe_prompt,
))
```

### Java

Uses `protoc-gen-grpc-java`. Add to `pom.xml`:

```xml
<plugin>
  <groupId>org.xolstice.maven.plugins</groupId>
  <artifactId>protobuf-maven-plugin</artifactId>
  <version>0.6.1</version>
  <configuration>
    <protocArtifact>com.google.protobuf:protoc:3.25.3:exe:${os.detected.classifier}</protocArtifact>
    <pluginId>grpc-java</pluginId>
    <pluginArtifact>io.grpc:protoc-gen-grpc-java:1.65.0:exe:${os.detected.classifier}</pluginArtifact>
    <protoSourceRoot>${project.basedir}/../../docs/api/grpc/proto</protoSourceRoot>
  </configuration>
  <executions>
    <execution>
      <goals><goal>compile</goal><goal>compile-custom</goal></goals>
    </execution>
  </executions>
</plugin>
```

### Go

```bash
make gen-proto-go   # runs protoc with protoc-gen-go and protoc-gen-go-grpc
```

Generated files appear in `api/grpc/ai/v1/`. Usage:

```go
import (
    "google.golang.org/grpc"
    aiv1 "github.com/yourorg/monorepo/api/grpc/ai/v1"
)

conn, _ := grpc.NewClient(cfg.AgentGRPCAddress, grpc.WithInsecure())
client := aiv1.NewAgentServiceClient(conn)
resp, err := client.SubmitTask(ctx, &aiv1.SubmitTaskRequest{
    RequestId: requestID,
    Prompt:    safePrompt,
})
```

---

## 4. Contract change workflow

Follow this sequence whenever you add or change any contract:

```
1. Update the contract file (openapi.yaml / asyncapi.yaml / .proto / .avsc)
2. Open a PR — contract changes are reviewed by the Tech Lead (CODEOWNERS)
3. Merge to main
4. Regenerate stubs in every affected language:
     make gen-api-client-ts        # frontend
     make gen-proto-go             # Go
     mvn generate-sources          # Java
     uv run openapi-python-client  # Python REST client (if applicable)
5. Run tests: make test-python && make test-java && make test-go && make test-frontend
6. Update CHANGELOG.md under the correct version
```

**Never regenerate on a feature branch that isn't the contract change itself.** Regeneration commits belong in the same PR as the contract change.

---

## 5. Verifying generated code is up-to-date in CI

CI runs a diff check to ensure generated files match the current contract:

```yaml
# .github/workflows/ci.yml (excerpt)
- name: Check generated code is up to date
  run: |
    make gen-proto-go gen-api-client-ts
    git diff --exit-code api/ frontend/web/src/lib/api/
```

If this step fails, someone changed a contract without regenerating. Regenerate and push.

---

## Quick reference

| Contract file                    | Generator                      | Make target                             |
| -------------------------------- | ------------------------------ | --------------------------------------- |
| `openapi.yaml` → TypeScript      | openapi-generator-cli          | `make gen-api-client-ts`                |
| `openapi.yaml` → Java stubs      | openapi-generator-maven-plugin | `make gen-sources-java SERVICE=<name>`  |
| `openapi.yaml` → Python client   | openapi-python-client          | `uv run openapi-python-client generate` |
| `openapi.yaml` → Go client       | oapi-codegen                   | `go generate ./...` in service dir      |
| `asyncapi.yaml` + `.avsc` → Java | avro-maven-plugin              | `make gen-sources-java SERVICE=<name>`  |
| `.proto` → Go                    | protoc-gen-go + grpc           | `make gen-proto-go`                     |
| `.proto` → Java                  | protoc-gen-grpc-java           | `make gen-sources-java SERVICE=<name>`  |
| `.proto` → Python                | grpcio-tools                   | `make gen-proto-python`                 |
