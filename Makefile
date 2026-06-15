IMAGE_NAME  ?= template-service
VERSION     ?= $(shell cat version.txt 2>/dev/null || echo "0.1.0")
REGISTRY    ?= ghcr.io/org
SERVICE     ?= api-gateway
APP         ?= web

.PHONY: setup setup-minimal setup-core setup-observability setup-full \
        infra-up infra-down infra-down-core infra-down-full infra-reset smoke \
        test-infra-up test-infra-down \
        test test-unit test-security lint format build \
        test-python test-unit-python test-security-python lint-python format-python build-python run run-python \
        guard-SERVICE \
        test-java test-unit-java lint-java lint-java-sca format-java build-java run-java \
        test-go test-unit-go lint-go format-go build-go run-go \
        test-frontend test-unit-frontend lint-frontend format-frontend build-frontend run-frontend \
        gen-proto-go gen-proto-python gen-sources-java gen-api-client-ts gen-api-client-python \
        gen-context-graph check-version check-versions check-placeholders doctor version \
        verify-f7-hook sync-develop \
        template-init init \
        new-service \
        deploy-staging rollback \
        docs-serve openapi-ui asyncapi-ui \
        sbom clean help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'

# ── Setup & Infrastructure ─────────────────────────────────────────────────

setup: ## [Deprecated alias → setup-core] Install deps, start core stack, run migrations
	@echo "Note: 'make setup' now maps to 'make setup-core'. Use setup-minimal / setup-core / setup-full to pick a profile."
	@$(MAKE) setup-core

setup-minimal: ## Solo/PoC — install deps, copy .env, run unit tests (NO Docker)
	@[ -f .env ] || cp .env.example .env
	uv sync --all-extras
	@$(MAKE) test-unit-python
	@echo "Minimal setup complete. Run 'make run' to start the API, or 'make smoke'."

setup-core: ## Product team — PostgreSQL + Redis + OTel + Prometheus + Grafana + Jaeger
	@$(MAKE) setup-minimal
	docker compose --profile core --profile observability up -d
	uv run alembic upgrade head
	@echo "Core setup complete. Run 'make smoke' to validate."

setup-observability: setup-core ## Alias for setup-core (observability is always included)

setup-full: ## Enterprise — full stack incl. Kafka, Schema Registry, flagd, Alertmanager
	@$(MAKE) setup-minimal
	docker compose --profile full up -d
	uv run alembic upgrade head
	@echo "Full setup complete. Run 'make smoke' to validate."

infra-up: ## Start the full shared infrastructure (all profiles — backwards-compatible)
	docker compose --profile full up -d

infra-down: ## Stop shared infrastructure (preserves volumes)
	docker compose --profile full down

infra-down-core: ## Stop the core + observability stack (preserves volumes)
	docker compose --profile core --profile observability down

infra-down-full: ## Stop the full stack (preserves volumes)
	docker compose --profile full down

infra-reset: ## Full infrastructure reset — stops containers AND wipes all volumes
	docker compose --profile full down -v

smoke: ## Post-setup validation for the active profile (health, deps, unit, lint)
	@bash scripts/smoke.sh

test-infra-up: ## Start lightweight integration-test infrastructure (offset ports)
	docker compose -f docker-compose.test.yml up -d

test-infra-down: ## Stop integration-test infrastructure and wipe test volumes
	docker compose -f docker-compose.test.yml down -v

# ── Python ─────────────────────────────────────────────────────────────────

test-python: ## Python: full test suite with coverage (unit + integration)
	PYTHONPATH=. uv run pytest tests/ --cov=src --cov-report=term-missing -q

test-unit-python: ## Python: unit tests only (no Docker required)
	PYTHONPATH=. uv run pytest tests/unit/ -q

test-security-python: ## Python: guardrail + PII leakage + OWASP-LLM checks
	PYTHONPATH=. uv run pytest tests/security/ -q

lint-python: ## Python: ruff lint + format-check (repo-wide, matches CI) + mypy + secret scan
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src/
	uv run detect-secrets scan --baseline .secrets.baseline

format-python: ## Python: auto-format with ruff (repo-wide, matches CI's format check)
	uv run ruff format .

build-python: ## Python: build multi-stage Docker image
	docker build --target production \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION) \
		-t $(REGISTRY)/$(IMAGE_NAME):latest .

run: ## Python: start FastAPI dev server with hot-reload (default)
	uv run uvicorn src.api.rest.main:app --reload --port 8000

run-python: run

# Legacy aliases (keep backward compatibility)
test: test-python
test-unit: test-unit-python
test-security: test-security-python
lint: lint-python
format: format-python
build: build-python

# ── Java ───────────────────────────────────────────────────────────────────

# NOTE: services are independent Maven projects (no root reactor pom), so each target
# `cd`s into the service dir and runs mvn there — matching .github/workflows/ci-java.yml
# (`(cd "$dir" && mvn ...)`). Do NOT use `-pl services/<name> -am` from the repo root:
# without a root aggregator pom it fails with "Could not find the selected project in the
# reactor". If a shared library is added later, `mvn install` it (or introduce a reactor pom).
# Fail loudly if SERVICE is unset/invalid (W1-7). Without this guard, `cd services/ && mvn ...`
# silently cd's into services/ (no pom) and the gate no-ops or errors cryptically — which is how
# Java lint/coverage went unenforced. Every per-service target below depends on this.
guard-SERVICE:
	@if [ -z "$(SERVICE)" ] || [ ! -d "services/$(SERVICE)" ]; then \
		echo "ERROR: SERVICE must name a service under services/ — got '$(SERVICE)'"; \
		echo "       (the default 'api-gateway' is the Python core in src/, not a services/ project)."; \
		echo "       e.g. make test-unit-java SERVICE=domain-service"; \
		echo "Available: $$(ls -d services/*/ 2>/dev/null | xargs -n1 basename | tr '\n' ' ')"; \
		exit 1; \
	fi

test-java: guard-SERVICE ## Java: full test suite with JaCoCo coverage (SERVICE=<name>)
	cd services/$(SERVICE) && mvn verify

test-unit-java: guard-SERVICE ## Java: unit tests only — no Testcontainers (SERVICE=<name>)
	cd services/$(SERVICE) && mvn test -Dsurefire.failIfNoSpecifiedTests=false

lint-java: guard-SERVICE ## Java: Checkstyle + SpotBugs — fast, no network (SERVICE=<name>)
	cd services/$(SERVICE) && mvn checkstyle:check spotbugs:check

# Split out of lint-java (W1-6 — bound agent actions). OWASP dependency-check downloads the full
# NVD feed: slow, and it can hang for tens of minutes or rate-limit (it once stalled a delivery
# agent ~50 min). Keep it OUT of the inner-loop / agent path. CI runs SCA as its own gate
# (.github/workflows/ci-java.yml); run this explicitly when you need a local SCA pass.
lint-java-sca: guard-SERVICE ## Java: OWASP dependency-check SCA only — slow, downloads NVD (SERVICE=<name>)
	cd services/$(SERVICE) && mvn dependency-check:check

format-java: guard-SERVICE ## Java: apply google-java-format via Maven plugin (SERVICE=<name>)
	cd services/$(SERVICE) && mvn fmt:format

build-java: guard-SERVICE ## Java: build Docker image (SERVICE=<name>)
	cd services/$(SERVICE) && mvn spring-boot:build-image \
		-Dspring-boot.build-image.imageName=$(REGISTRY)/$(SERVICE):$(VERSION)

run-java: guard-SERVICE ## Java: start Spring Boot dev server (SERVICE=<name>)
	cd services/$(SERVICE) && mvn spring-boot:run

# ── Go ─────────────────────────────────────────────────────────────────────

test-go: guard-SERVICE ## Go: full test suite with race detector + coverage
	go test -race -coverprofile=coverage.out ./services/$(SERVICE)/...
	go tool cover -func=coverage.out | tail -1

test-unit-go: guard-SERVICE ## Go: unit tests only (skips integration tests)
	go test -short ./services/$(SERVICE)/...

lint-go: guard-SERVICE ## Go: golangci-lint (staticcheck + errcheck + gosec)
	golangci-lint run ./services/$(SERVICE)/...

format-go: guard-SERVICE ## Go: gofmt + goimports
	gofmt -w services/$(SERVICE)/
	goimports -w services/$(SERVICE)/

build-go: ## Go: build Docker image (SERVICE=<name>)
	docker build -f services/$(SERVICE)/Dockerfile \
		-t $(REGISTRY)/$(SERVICE):$(VERSION) \
		-t $(REGISTRY)/$(SERVICE):latest .

run-go: ## Go: start service with air hot-reload (SERVICE=<name>)
	air -c services/$(SERVICE)/.air.toml

gen-proto-go: ## Go: regenerate gRPC stubs into api/grpc/ (path derived from each proto's go_package)
	# module= mode honours the proto `option go_package` (…/api/grpc/ai/v1) and strips the
	# module prefix, so stubs land at api/grpc/ai/v1/ — matching the committed location the
	# CI stub-drift check looks for. (paths=source_relative wrongly wrote to the repo root.)
	find docs/api/grpc/proto -name "*.proto" | xargs \
		protoc --go_out=. --go_opt=module=github.com/yourorg/monorepo \
		       --go-grpc_out=. --go-grpc_opt=module=github.com/yourorg/monorepo \
		       -I docs/api/grpc/proto

gen-proto-python: ## Python: regenerate gRPC stubs from proto files into src/shared/generated/grpc/
	mkdir -p src/shared/generated/grpc
	find docs/api/grpc/proto -name "*.proto" | xargs \
		uv run python -m grpc_tools.protoc \
		-I docs/api/grpc/proto \
		--python_out=src/shared/generated/grpc \
		--grpc_python_out=src/shared/generated/grpc

gen-sources-java: guard-SERVICE ## Java: run mvn generate-sources (OpenAPI stubs + Avro classes) (SERVICE=<name>)
	cd services/$(SERVICE) && mvn generate-sources

gen-api-client-python: ## Python: regenerate REST client from OpenAPI spec into src/shared/generated/rest_client/
	uv run openapi-python-client generate \
		--path docs/api/openapi/v1/openapi.yaml \
		--output-path src/shared/generated/rest_client \
		--overwrite

gen-context-graph: ## Generate .agent/context-graph.json for agent session bootstrap (ADR-0057)
	uv run python scripts/generate_context_graph.py

check-version: ## Verify version.txt is the single source of truth (ADR-0057)
	uv run python scripts/check_version_consistency.py

check-versions: ## Verify installed runtimes meet minimum versions (Python/Java/Go/Node/uv)
	@bash scripts/check-versions.sh

check-placeholders: ## Detect unresolved template placeholder strings
	@bash scripts/check-template-placeholders.sh

check-control-bindings: ## Control-binding gate (ADR-0061). BASE=main DECLARED=<file> | BINDINGS="..."
	@uv run python scripts/governance/check_control_bindings.py --local --base $${BASE:-main} \
		$${DECLARED:+--declared "$$DECLARED"} $${BINDINGS:+--declared-text "$$BINDINGS"}

check-action-pins: ## Fail if any GitHub Actions `uses:` is not SHA-pinned (RFC-0015)
	@bash scripts/governance/check_action_pins.sh

burn-in-status: ## Report a report-mode gate's burn-in progress toward blocking (ADR-0070). GATE=<target>
	@python3 scripts/governance/burn_in_status.py $${GATE:+--gate "$$GATE"}

check-control-matrix: ## Validate the security control matrices — paths/CI jobs exist, n/a justified (ADR-0072)
	@uv run python scripts/governance/check_control_matrix.py

check-slo-thresholds: ## Fail if canary/error-budget thresholds are hard-coded in workflow YAML (ADR-0073)
	@uv run python scripts/governance/check_slo_thresholds.py

check-outbound-urls: ## Fail if an outbound-HTTP boundary skips the SSRF allow-list (OWASP A10)
	@uv run python scripts/governance/check_outbound_urls.py

check-inline-prompts: ## Fail if a NEW inline LLM system prompt appears in src/agents/ (ADR-0079)
	@uv run python scripts/governance/check_inline_prompts.py

verify-traceability: ## Verify service→ADR→topic→schema→SLO→runbook traceability chain (Wave 1)
	@uv run python scripts/governance/check_traceability.py
	@uv run python scripts/governance/check_service_slo_files.py
	@uv run python scripts/governance/check_runbook_links.py

verify-f7-hook: ## Verify the F7 high-risk-action guard hook (decision logic + settings.json wiring; issue #133)
	@python3 .claude/hooks/verify-high-risk-guard.py

template-init: ## First-run init — replaces placeholders. PROJECT_NAME= ORG= REGISTRY= [PROFILE=full] [PACKAGE_ROOT=com.x]
	@[ -n "$(PROJECT_NAME)" ] || (echo "ERROR: PROJECT_NAME is required" && exit 1)
	@[ -n "$(ORG)" ]         || (echo "ERROR: ORG is required"          && exit 1)
	@[ -n "$(REGISTRY)" ]    || (echo "ERROR: REGISTRY is required"     && exit 1)
	@bash scripts/template-init.sh \
	  "$(PROJECT_NAME)" "$(ORG)" "$(REGISTRY)" "$(or $(PROFILE),full)" "$(PACKAGE_ROOT)"

init: template-init ## Alias for template-init

doctor: ## Validate local environment before setup (tools, .env, ports, placeholders)
	@bash scripts/doctor.sh

version: ## Print the canonical project version (version.txt — single source, ADR-0057)
	@cat version.txt

sync-develop: ## Fast-forward develop to origin/main and push (ff-only — never force/merge)
	@git fetch origin --prune --quiet
	@git rev-parse --verify --quiet develop >/dev/null || { echo "✗ no local 'develop' branch"; exit 1; }
	@if [ "$$(git rev-list --count origin/main..develop)" != "0" ]; then \
		echo "✗ develop has commits not in origin/main — refusing to auto-sync; reconcile manually"; exit 1; \
	fi
	@if [ "$$(git symbolic-ref --short HEAD 2>/dev/null)" = "develop" ]; then \
		git merge --ff-only origin/main; \
	else \
		git fetch . origin/main:develop; \
	fi
	@git push origin develop
	@echo "✓ develop synced to origin/main ($$(git rev-parse --short develop))"

# ── Frontend ───────────────────────────────────────────────────────────────

test-frontend: ## Frontend: Jest unit + Playwright e2e tests (APP=<name>)
	cd frontend/$(APP) && pnpm test && pnpm e2e

test-unit-frontend: ## Frontend: Jest unit tests only (APP=<name>)
	cd frontend/$(APP) && pnpm test:unit

lint-frontend: ## Frontend: ESLint + TypeScript type check (APP=<name>)
	cd frontend/$(APP) && pnpm lint && pnpm type-check

format-frontend: ## Frontend: Prettier format (APP=<name>)
	cd frontend/$(APP) && pnpm format

build-frontend: ## Frontend: Next.js production build (APP=<name>)
	cd frontend/$(APP) && pnpm build

run-frontend: ## Frontend: Next.js dev server with hot-reload (APP=<name>)
	cd frontend/$(APP) && pnpm dev

gen-api-client-ts: ## Frontend: regenerate TypeScript API client from OpenAPI spec
	npx @openapitools/openapi-generator-cli generate \
		-i docs/api/openapi/v1/openapi.yaml \
		-g typescript-fetch \
		-o frontend/$(APP)/src/lib/api \
		--additional-properties=typescriptThreePlus=true,supportsES6=true,withoutRuntimeChecks=true

# ── Deploy ─────────────────────────────────────────────────────────────────

deploy-staging: ## Build, push, and deploy to staging (SERVICE=<name>)
	docker push $(REGISTRY)/$(SERVICE):$(VERSION)
	helm upgrade --install $(SERVICE) ./infrastructure/helm/$(SERVICE) \
		--namespace staging \
		--values infrastructure/helm/$(SERVICE)/values-staging.yaml \
		--set image.tag=$(VERSION) \
		--wait

rollback: ## Rollback the last staging deploy
	bash infrastructure/scripts/deploy/rollback.sh --env=staging

# ── Docs & Contracts ───────────────────────────────────────────────────────

docs-serve: ## Serve MkDocs documentation locally
	uv run mkdocs serve

openapi-ui: ## Open Swagger UI for the REST API contract
	npx swagger-ui-watcher docs/api/openapi/v1/openapi.yaml --port 8082

asyncapi-ui: ## Open AsyncAPI Studio for the event contract
	npx @asyncapi/cli preview docs/api/asyncapi/v1/asyncapi.yaml --port 8083

# ── Service Scaffold ───────────────────────────────────────────────────────

new-service: ## Scaffold a new service. NAME= LANG=python|java|go [OWNER=team] [PORT=8010] [REGISTER=true]
	@[ -n "$(NAME)" ] || (echo "ERROR: NAME is required" && exit 1)
	@[ -n "$(LANG)" ] || (echo "ERROR: LANG is required" && exit 1)
	@bash scripts/new-service.sh \
	  "$(NAME)" "$(LANG)" "$(or $(OWNER),platform-team)" "$(or $(PORT),8010)" "$(or $(REGISTER),false)"

# ── Utilities ──────────────────────────────────────────────────────────────

sbom: ## Generate signed Software Bill of Materials
	syft . -o cyclonedx-json=sbom.cyclonedx.json

agent-feedback-check: ## Check feedback loop convergence — queries Prometheus for HITL bias state
	@echo "=== Agent Feedback Loop — Current Bias State ==="
	@curl -sf "$(or $(PROMETHEUS_URL),http://localhost:9090)/api/v1/query?query=agent_feedback_bias_applied" \
		| python3 -c "import sys,json; d=json.load(sys.stdin); \
		  results=d.get('data',{}).get('result',[]); \
		  [print(f\"  {r['metric'].get('action_type','?'):30s} bias={float(r['value'][1]):.2f}\") for r in results] \
		  or print('  (no bias adjustments recorded yet)')"
	@echo ""
	@echo "=== HITL Rejection Rates ==="
	@curl -sf "$(or $(PROMETHEUS_URL),http://localhost:9090)/api/v1/query?query=agent_feedback_rejection_rate" \
		| python3 -c "import sys,json; d=json.load(sys.stdin); \
		  results=d.get('data',{}).get('result',[]); \
		  [print(f\"  {r['metric'].get('action_type','?'):30s} rejection_rate={float(r['value'][1]):.1%}\") for r in results] \
		  or print('  (no data — Prometheus may not be running)')"
	@echo ""
	@echo "=== Adjustments Counter ==="
	@curl -sf "$(or $(PROMETHEUS_URL),http://localhost:9090)/api/v1/query?query=agent_feedback_adjustments_total" \
		| python3 -c "import sys,json; d=json.load(sys.stdin); \
		  results=d.get('data',{}).get('result',[]); \
		  [print(f\"  {r['metric'].get('action_type','?'):30s} dir={r['metric'].get('direction','?'):4s} count={r['value'][1]}\") for r in results] \
		  or print('  (no adjustments made yet)')"

agentic-maturity-check: ## Evaluate repo against Gartner 4-level maturity model (informational)
	@python3 scripts/agentic_maturity_check.py

clean: ## Remove all build artefacts and caches
	rm -rf dist/ build/ htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/ coverage.out
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name target -maxdepth 4 -exec rm -rf {} + 2>/dev/null || true
