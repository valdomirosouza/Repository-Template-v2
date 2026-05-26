# Adding a New Service

> **Read first:** [docs/quickstart/README.md](README.md) and your language guide before starting.

This checklist covers every step required to register a new service in the monorepo — from directory creation to CI and deployment. Work through it top-to-bottom; each step must be completed before the next.

---

## Step 0 — Decide the language

Consult ADR-0016 (Language selection) before choosing. The short version:

| Use Python when...                | Use Java when...                  | Use Go when...                         |
| --------------------------------- | --------------------------------- | -------------------------------------- |
| The service calls an LLM          | The service owns a complex domain | Throughput > 10k events/s              |
| It needs HITL / guardrails        | It needs JPA / rich ORM           | It is a sidecar or infrastructure glue |
| It is an AI agent or orchestrator | It exposes a rich REST domain API | It needs very low memory footprint     |

---

## Step 1 — Scaffold the directory structure

```bash
# Option A: use the make target (recommended)
make new-service NAME=<your-service> LANG=<python|java|go>

# Option B: create manually
```

**Python:**

```bash
mkdir -p src/agents/<your-service>   # if it's an AI agent
# OR
mkdir -p src/api/rest/routers        # if adding a new router to the API gateway
```

**Java:**

```bash
mkdir -p services/<your-service>/src/main/java/com/yourorg/<yourservice>/{api,domain,infra,config}
mkdir -p services/<your-service>/src/main/resources
mkdir -p services/<your-service>/src/test/java/com/yourorg/<yourservice>/{unit,integration}
```

**Go:**

```bash
mkdir -p services/<your-service>/cmd/<your-service>
mkdir -p services/<your-service>/internal/{handler,domain,infra,config}
touch services/<your-service>/go.mod  # initialise with: go mod init github.com/yourorg/monorepo/services/<your-service>
```

---

## Step 2 — Register in `services.yaml`

Open `services.yaml` at the repo root and add an entry:

```yaml
- name: <your-service>
  language: python | java | go | nodejs
  type: api | worker | job | frontend
  port: <port> # pick an unused port; document in this file
  image: yourorg/<your-service>
  owner: <team-name>
  publishes:
    - <topic-name>.v1 # only if the service produces Kafka events
  subscribes:
    - <topic-name>.v1 # only if the service consumes Kafka events
  depends_on:
    - api-gateway # list runtime REST/gRPC dependencies
  adr:
    - ADR-0002 # always include the stack selection ADR
```

If the service publishes events, also add the topic to the `topics:` section with schema path, partitions, and retention.

---

## Step 3 — Claim ownership in CODEOWNERS

Open `.github/CODEOWNERS` and add a line:

```
services/<your-service>/     @yourorg/<team-name>
```

For Python services extending the API gateway:

```
src/agents/<your-service>/   @yourorg/<team-name>
```

---

## Step 4 — Wire into Prometheus scrape config

Open `infrastructure/monitoring/prometheus/prometheus.yml` and add a job:

```yaml
- job_name: <your-service>
  static_configs:
    - targets: ["host.docker.internal:<port>"]
  metrics_path: /metrics # Python/Go
  # metrics_path: /actuator/prometheus   # Java
  relabel_configs:
    - target_label: service
      replacement: <your-service>
    - target_label: language
      replacement: <python|java|go>
```

---

## Step 5 — Create Kubernetes manifests

Copy and adapt the template manifests:

```bash
cp infrastructure/k8s/deployment.yaml infrastructure/k8s/<your-service>-deployment.yaml
cp infrastructure/k8s/service.yaml    infrastructure/k8s/<your-service>-service.yaml
```

Mandatory changes in the deployment:

- `metadata.name` → `<your-service>`
- `spec.template.spec.containers[0].image` → `yourorg/<your-service>:latest`
- `spec.template.spec.containers[0].ports[0].containerPort` → your port
- `startupProbe.httpGet.port` → your port
- `livenessProbe.httpGet.port` → your port
- `readinessProbe.httpGet.port` → your port
- All `app: agent-service` label selectors → `app: <your-service>`

Do **not** remove the three probes (startupProbe, livenessProbe, readinessProbe). See `docs/runbooks/RB-003-hitl-recovery.md` before changing probe thresholds.

---

## Step 6 — Add environment variables

If the service needs new environment variables beyond what is in `.env.example`:

1. Add them to `.env.example` with `[REQUIRED]` or `[OPTIONAL]` markers and a comment indicating which language/service they apply to.
2. Add them to the relevant `src/shared/config.py` (Python) or `application.yml` (Java) or `envconfig` struct (Go).
3. Add them to the K8s deployment manifest under `env:` or `envFrom:`.

Never hardcode values — every config item must come from an environment variable.

---

## Step 7 — Wire into CI

**Python services** are already covered by `ci.yml` — no changes needed.

**Java services:** `ci-java.yml` auto-discovers any `services/*/pom.xml` — no changes needed as long as your service follows the standard Maven layout.

**Go services:** `ci-go.yml` auto-discovers any `services/*/go.mod` — no changes needed.

**Frontend apps:** Open `.github/workflows/ci-frontend.yml` and add your app name to the matrix:

```yaml
strategy:
  matrix:
    app: [frontend, <your-app>] # add here
```

---

## Step 8 — Create the service Dockerfile

**Python** — reuse the existing multi-stage Dockerfile with a different entrypoint (override `CMD` in the deployment manifest).

**Java:**

```dockerfile
FROM eclipse-temurin:21-jre-alpine AS production
WORKDIR /app
ARG JAR_FILE=target/*.jar
COPY ${JAR_FILE} app.jar
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
EXPOSE <port>
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://localhost:<port>/actuator/health || exit 1
ENTRYPOINT ["java", "-jar", "app.jar"]
```

**Go:**

```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /app ./cmd/<your-service>

FROM scratch AS production
COPY --from=builder /app /app
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE <port>
ENTRYPOINT ["/app"]
```

---

## Step 9 — Write the spec first

Per SDD rules (CLAUDE.md §2), no code is written without a referenced spec.

Create `specs/system/<your-service>.md` with at minimum:

- **Purpose:** what problem this service solves
- **Inputs:** REST endpoints, Kafka topics consumed, gRPC methods
- **Outputs:** REST responses, Kafka topics published, side effects
- **Non-goals:** explicitly list what the service does NOT do
- **SLO:** latency p99, error rate, availability target
- **HITL requirement:** does this service execute agent actions? If yes, which ones?

---

## Step 10 — Day-1 PR checklist

Before opening the first PR for your new service:

- [ ] `services.yaml` updated with the new service entry
- [ ] `.github/CODEOWNERS` updated
- [ ] `infrastructure/monitoring/prometheus/prometheus.yml` updated
- [ ] K8s manifests created (deployment, service)
- [ ] Dockerfile written and builds locally
- [ ] `.env.example` updated with new env vars (if any)
- [ ] Spec written at `specs/system/<your-service>.md`
- [ ] Unit tests written and coverage ≥ 80%
- [ ] CI workflow updated (frontend only — Java/Go auto-discovered)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] `make test-<lang>` passes locally
- [ ] `make lint-<lang>` passes locally
- [ ] No real PII in any test fixture or log statement
- [ ] `ANTHROPIC_API_KEY` and `SECRET_KEY` not hardcoded anywhere
- [ ] Service README.md written (see jobs-worker.md for required sections)

---

## Quick reference — ports in use

| Service        | Port | Language |
| -------------- | ---- | -------- |
| api-gateway    | 8000 | Python   |
| domain-service | 8080 | Java     |
| event-worker   | 8090 | Go       |
| frontend       | 3000 | Node.js  |

Add your service to this table in `services.yaml` (the table here is illustrative — `services.yaml` is authoritative).

---

## Scaffold helper

```bash
# Create all boilerplate for a new service in one command
make new-service NAME=<your-service> LANG=<python|java|go>

# What it creates:
#   services/<name>/           directory structure for the chosen language
#   services/<name>/README.md  service README with required sections pre-filled
#   infrastructure/k8s/<name>-deployment.yaml
#   infrastructure/k8s/<name>-service.yaml
# What it does NOT do:
#   Register in services.yaml    ← you must do this (Step 2)
#   Update CODEOWNERS            ← you must do this (Step 3)
#   Update prometheus.yml        ← you must do this (Step 4)
```
