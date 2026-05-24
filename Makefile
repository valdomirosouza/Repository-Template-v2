IMAGE_NAME  ?= template-service
VERSION     ?= $(shell cat version.txt 2>/dev/null || echo "0.1.0")
REGISTRY    ?= ghcr.io/org

.PHONY: setup test test-unit test-security lint format build \
        deploy-staging rollback docs-serve openapi-ui asyncapi-ui \
        sbom clean help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Install deps, copy .env, start stack, run migrations
	uv sync
	@[ -f .env ] || cp .env.example .env
	docker compose up -d
	uv run alembic upgrade head

test: ## Full test suite with coverage (unit + integration)
	uv run pytest tests/ --cov=src --cov-report=term-missing -q

test-unit: ## Unit tests only
	uv run pytest tests/unit/ -q

test-security: ## Defensive validation suite (guardrail + PII leakage checks)
	uv run pytest tests/security/ -q

lint: ## Ruff lint + mypy type-check + secret scan
	uv run ruff check src/ tests/
	uv run mypy src/
	uv run detect-secrets scan --baseline .secrets.baseline

format: ## Auto-format with ruff
	uv run ruff format src/ tests/

build: ## Build multi-stage Docker image
	docker build --target production \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION) \
		-t $(REGISTRY)/$(IMAGE_NAME):latest .

deploy-staging: build ## Build, push, and deploy to staging
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	helm upgrade --install $(IMAGE_NAME) ./infrastructure/helm/$(IMAGE_NAME) \
		--namespace staging \
		--values infrastructure/helm/$(IMAGE_NAME)/values-staging.yaml \
		--set image.tag=$(VERSION) \
		--wait

rollback: ## Rollback the last staging deploy
	bash infrastructure/scripts/deploy/rollback.sh --env=staging

docs-serve: ## Serve MkDocs documentation locally
	uv run mkdocs serve

openapi-ui: ## Open Swagger UI for REST API
	npx swagger-ui-watcher docs/api/openapi/v1/openapi.yaml --port 8080

asyncapi-ui: ## Open AsyncAPI Studio for event contracts
	npx @asyncapi/cli preview docs/api/asyncapi/v1/asyncapi.yaml --port 8081

sbom: ## Generate signed Software Bill of Materials
	syft . -o cyclonedx-json=sbom.cyclonedx.json

clean: ## Remove build artefacts and caches
	rm -rf dist/ build/ htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
