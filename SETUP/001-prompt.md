# Prompt 001 — Directory Scaffold

> **Run this first.** Creates every directory in the monorepo tree and places a
> `.gitkeep` in each empty leaf so git preserves the structure.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Section "Repository Structure").

---

## Task

Read `MONOREPO-STRUCTURE-EN.md` in full, then create **all directories** defined in
the repository tree. Place a `.gitkeep` file in every empty leaf directory
(i.e., directories that will not immediately receive a content file in this prompt).

### Directory list

```
docs/adr/
docs/api/openapi/v1/
docs/api/openapi/v2/
docs/api/asyncapi/v1/
docs/api/grpc/proto/
docs/runbooks/
docs/postmortems/
docs/security/pentest-reports/
docs/privacy/dpia/
docs/privacy/ripd/
docs/ai-governance/
docs/sre/slo/
docs/sre/prr/
docs/sre/cuj/
docs/change-management/rfc/
src/agents/orchestrator/
src/api/rest/routers/
src/api/rest/middleware/
src/api/async/consumers/
src/api/async/producers/
src/api/async/schemas/
src/api/grpc/generated/
src/memory/
src/guardrails/
src/observability/
src/shared/
tests/unit/agents/
tests/unit/guardrails/
tests/unit/api/
tests/integration/
tests/e2e/
tests/contract/pacts/
tests/performance/k6/
tests/performance/benchmarks/
tests/security/
tests/chaos/experiments/
tests/chaos/runbooks/
tests/fixtures/
infrastructure/terraform/modules/kubernetes/
infrastructure/terraform/modules/message-broker/
infrastructure/terraform/modules/cache/
infrastructure/terraform/modules/vector-db/
infrastructure/terraform/modules/observability/
infrastructure/terraform/modules/networking/
infrastructure/terraform/environments/dev/
infrastructure/terraform/environments/staging/
infrastructure/terraform/environments/production/
infrastructure/helm/
infrastructure/monitoring/prometheus/rules/
infrastructure/monitoring/grafana/dashboards/cuj-dashboards/
infrastructure/monitoring/grafana/alerts/
infrastructure/monitoring/jaeger/
infrastructure/monitoring/opentelemetry/
infrastructure/message-broker/topics/
infrastructure/message-broker/schema-registry/avro/
infrastructure/feature-flags/flags/
infrastructure/scripts/deploy/
infrastructure/scripts/db/
harness/
.github/workflows/
.github/ISSUE_TEMPLATE/
skills/domain/
skills/sdlc/
skills/observability/
skills/devsecops/
skills/sre/
skills/api/
skills/change-management/
skills/ai/
skills/privacy/
skills/ethics/
skills/engineering/
specs/system/
specs/sdlc/
specs/observability/
specs/api/
specs/security/
specs/ai/
specs/privacy/
specs/ethics/
.devcontainer/
```

### Validation

After creating all directories, confirm:

- Every directory in the list above exists
- Every empty leaf directory has a `.gitkeep` file
- Output a count: directories created, `.gitkeep` files placed
