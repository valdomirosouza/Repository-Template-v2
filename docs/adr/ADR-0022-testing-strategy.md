# ADR-0022 — Testing Strategy

**Status:** Accepted
**Date:** 2026-05-28
**Authors:** Tech Lead, QA Lead
**Spec:** `specs/sdlc/development-lifecycle.md`
**Supersedes:** None | **Superseded by:** None

---

## Context

The monorepo contains five services across four languages (Python, Java, Go, TypeScript/Next.js)
and an AI agents extension with non-deterministic behaviour. Previous waves established CI gates
(`harness/code-check.yml` enforcing 80% Python coverage) but left the following gaps:

1. No `[tool.coverage]` section in `pyproject.toml` — the 80% threshold was enforced only in
   the CI harness, not when running `make test-unit-python` locally. Developers could not
   verify coverage compliance before pushing.
2. Branch coverage was not tracked — conditional logic paths went unexercised without failing CI.
3. The test pyramid was implicit. There was no canonical document mapping test types to
   directories, markers, and infrastructure requirements.
4. Contract testing between services (REST, Kafka) had no defined approach. The harness
   contract tests (`tests/contract/test_harness_contracts.py`) existed but were not generalised
   to service-to-service REST contracts.
5. Mutation testing had no recommended tooling or target thresholds.

---

## Decision

### 1. Test Pyramid

Six test layers are defined, each with an assigned directory, pytest marker, and infrastructure requirement:

| Layer       | Directory            | Marker        | Infrastructure  | Coverage counted |
| ----------- | -------------------- | ------------- | --------------- | ---------------- |
| Unit        | `tests/unit/`        | `unit`        | None            | Yes              |
| Integration | `tests/integration/` | `integration` | Full stack      | Yes              |
| Security    | `tests/security/`    | `security`    | None (mocks)    | Yes              |
| Contract    | `tests/contract/`    | `unit`        | None            | Yes              |
| Performance | `tests/performance/` | N/A           | Full stack      | No               |
| Chaos       | `tests/chaos/`       | `chaos`       | Full stack      | No               |
| E2E         | `tests/e2e/`         | N/A           | Full stack + UI | No               |

Contract tests reuse the `unit` marker because they are fast and require no live services.
Performance, chaos, and E2E tests are excluded from coverage accounting.

### 2. Coverage Thresholds

- **Line coverage:** ≥ 80% for all code under `src/`, enforced in both CI and locally.
- **Branch coverage:** enabled — conditional branches must be exercised or explicitly excluded.
- **Omit list:** `src/shared/generated/` (generated gRPC stubs), `alembic/` migrations,
  `src/api/rest/main.py` lifespan startup hooks (infrastructure wiring, not business logic).

These thresholds are declared in `pyproject.toml [tool.coverage]` so that any invocation of
`pytest --cov=src` — including `make test-unit-python` — enforces them consistently.

**Why 80% and not higher:**

80% is sufficient to catch most regressions in business logic while leaving room for
infrastructure wiring code and error paths that are hard to unit-test without mocking the
entire stack. The integration and chaos layers cover the gaps that unit tests cannot reach.
Raising the threshold without adding meaningful tests creates pressure to write coverage-padding
tests rather than valuable ones.

### 3. Contract Testing Approach

**In-process schema contracts** (agent harness):

- `tests/contract/test_harness_contracts.py` validates that message schemas between
  Planner → Generator → Evaluator conform to `src/agents/harness/models.py`.
- These run as `unit`-marked tests with no I/O.

**REST consumer-driven contracts** (inter-service REST):

- Pact is the chosen tool for consumer-driven contract testing between frontend and api-gateway.
- Consumer-side tests generate Pact JSON files in `tests/contract/pacts/`.
- Provider-side verification runs in `ci.yml` to prevent breaking changes from shipping.
- Implementation deferred to Wave 6.

**Why Pact over alternatives:**

| Option                  | Reason not chosen                                                |
| ----------------------- | ---------------------------------------------------------------- |
| OpenAPI validation only | Validates schema but not semantic contracts (e.g., status codes) |
| Integration tests       | Requires both services running; slow and fragile in CI           |
| Postman/Newman          | No consumer-driven model; contracts live outside the codebase    |
| Pact                    | Consumer-driven, language-agnostic, runs without live services   |

### 4. Mutation Testing

Mutation testing is **recommended but not gated**. The tooling is `mutmut`.

Target mutation scores for critical modules:

| Module                         | Target score |
| ------------------------------ | ------------ |
| `src/agents/hitl_gateway.py`   | ≥ 70%        |
| `src/guardrails/pii_filter.py` | ≥ 70%        |
| `src/agents/risk_scorer.py`    | ≥ 70%        |
| `src/agents/feedback_loop.py`  | ≥ 60%        |

Mutation testing is run manually before major releases, not on every PR. The rationale: mutation
testing on every PR would increase CI time by 10–30× for marginal incremental benefit over the
80% coverage gate.

### 5. Multi-Language Testing

Each language follows its own pyramid aligned with this strategy:

| Language   | Unit runner | Coverage tool            | Integration                   | E2E        |
| ---------- | ----------- | ------------------------ | ----------------------------- | ---------- |
| Python     | pytest      | pytest-cov               | pytest                        | Playwright |
| Java       | JUnit 5     | JaCoCo (≥ 80%)           | Testcontainers                | N/A        |
| Go         | `go test`   | `go test -cover` (≥ 80%) | `go test` with Testcontainers | N/A        |
| TypeScript | Jest        | Jest coverage (≥ 80%)    | N/A                           | Playwright |

Coverage thresholds for Java and Go are configured in their respective build tools
(`pom.xml` JaCoCo plugin and `Makefile` coverage flag). TypeScript coverage is configured
in `jest.config.ts`.

---

## Consequences

### Positive

- Developers catch coverage regressions before pushing — no surprise CI failures.
- Branch coverage eliminates the "line touched but never exercised" category of gaps.
- A documented pyramid reduces debate about which test layer owns a given scenario.
- Pact contracts prevent frontend from breaking when api-gateway response shapes change.

### Negative / Trade-offs

- Adding `fail_under=80` to `pyproject.toml` will fail the build for any developer whose
  local changes drop coverage below 80% — this is intentional but requires awareness.
- Branch coverage increases the number of required test cases for code with multiple branches.
  This is accepted: untested branches are bugs waiting to happen in production.
- Pact introduces a Pact Broker dependency for publishing contracts across services.
  For Wave 6, pact files are committed to the repository as JSON; a Pact Broker is optional
  until there are more than two service pairs.

---

## Alternatives Considered

**No local coverage enforcement (status quo):**
Rejected: the gap between CI enforcement and local feedback led to late-cycle coverage failures
and developer frustration. Closing the gap at low cost (one `pyproject.toml` section) is worth it.

**100% coverage target:**
Rejected: 100% creates perverse incentives to write trivial tests for generated code and
infrastructure bootstrapping. 80% with branch coverage and a mutation testing recommendation
provides better signal.

**Jest-only for contract testing:**
Rejected: Jest tests require both services to be available as test doubles. Pact's consumer-driven
model isolates the contract test from infrastructure.
