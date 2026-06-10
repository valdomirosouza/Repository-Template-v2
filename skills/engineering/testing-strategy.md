# Skill — Testing Strategy

**Owner:** Tech Lead | **Reviewer:** QA Lead | **Status:** Active | **Last updated:** 2026-05-28

Activate this skill when writing, reviewing, or troubleshooting tests — or when deciding which test layer applies to a given scenario.

See also: `docs/adr/ADR-0022-testing-strategy.md` for the architectural rationale behind these decisions.

---

## Test Pyramid

```
         ┌──────────┐
         │   E2E    │  tests/e2e/        — Playwright (UI flows, HITL operator journeys)
        ┌┴──────────┴┐
        │  Contract  │  tests/contract/  — Pact (inter-service API contracts)
       ┌┴────────────┴┐
       │  Performance │  tests/performance/ — k6 (load, spike), benchmarks (Python hot paths)
      ┌┴──────────────┴┐
      │    Chaos       │  tests/chaos/    — fault injection, game-day playbook
     ┌┴────────────────┴┐
     │   Integration    │  tests/integration/ — real services (Postgres, Redis, Kafka via Docker)
    ┌┴──────────────────┴┐
    │       Unit         │  tests/unit/    — fast, no I/O, run anywhere
    └────────────────────┘
```

**Rule:** Write tests at the lowest layer that gives you confidence. Only go higher when the lower layer cannot catch the bug.

---

## Pytest Markers

Every test must declare exactly one marker. `--strict-markers` enforces this in CI.

| Marker        | Meaning                               | Infrastructure required | Typical run time |
| ------------- | ------------------------------------- | ----------------------- | ---------------- |
| `unit`        | Fast, pure logic, no I/O              | None                    | < 100 ms/test    |
| `integration` | Hits real services via Docker Compose | Postgres, Redis, Kafka  | 1–10 s/test      |
| `security`    | Defensive validation (PII, injection) | None (uses mocks)       | < 500 ms/test    |
| `chaos`       | Fault injection, game-day             | Full stack              | Minutes          |

```python
import pytest

@pytest.mark.unit
def test_risk_scorer_high_risk_action() -> None: ...

@pytest.mark.integration
async def test_redis_hitl_store_round_trip() -> None: ...

@pytest.mark.security
def test_pii_filter_masks_email() -> None: ...

@pytest.mark.chaos
async def test_request_consumer_survives_kafka_outage() -> None: ...
```

---

## Coverage Requirements

**Minimum:** 80% line coverage for all code under `src/`.
**Branch coverage:** enabled — conditional logic paths must be exercised.

Coverage is enforced in two places:

1. **CI gate** — `harness/code-check.yml` runs `pytest --cov=src --cov-fail-under=80`
2. **Locally** — `pyproject.toml [tool.coverage]` section enforces the same threshold on `make test-unit-python`

To check coverage locally:

```bash
make test-unit-python        # runs with --cov; fails if < 80%
uv run pytest tests/unit/ --cov=src --cov-report=html   # detailed HTML report
open htmlcov/index.html
```

**What counts toward coverage:** all Python modules under `src/` except generated stubs (`src/shared/generated/`).

---

## Test-Integrity Invariants (ADR-0065)

Coverage is a **quantity** metric — it is fully satisfiable while the suite's integrity erodes
(weak tests added, strong assertions gutted, flaky tests skipped). These four invariants guard the
integrity coverage cannot see. Two are **machine-enforced** by
`scripts/governance/check_test_integrity.py` (wired into `harness/code-check.yml`); two are
**review-time** rules.

1. **RED before GREEN** _(review-time)._ Write the test, **confirm it fails**, then implement until
   it passes. A test that passes on first write is too weak to constrain the code — strengthen it.
2. **Test co-location** _(review-time)._ Tests ship in the **same task/commit** as the code they
   cover. "Tested in a later task/PR" is **test deferral** — an anti-pattern (one task = one
   reviewable artifact, ADR-0060).
3. **No silent test-count decrease** _(enforced)._ The gate compares per-marker + total test counts
   against `tests/.test-integrity-baseline.json`. A decrease **fails the PR** unless a
   `TEST-WAIVER: <reason>` line is present (PR body or diff) **and** the baseline is refreshed:

   ```bash
   uv run python scripts/governance/check_test_integrity.py            # check vs baseline
   uv run python scripts/governance/check_test_integrity.py --update-baseline   # after an intended change
   ```

4. **No assertion weakening / silent skip** _(enforced for added skips)._ A newly added
   `@pytest.mark.skip|xfail|skipif`, `pytest.skip(...)`, or `@unittest.skip` **must** carry a
   rationale — `reason="…"`, a string argument, or an inline `# why` comment — or the PR fails.
   Never weaken or disable an assertion to make a gate go green: **tests are the spec; the
   implementation conforms to the tests**, not the reverse.

The RED-first flow in practice: a sub-task writes its failing test(s) first (RED), implements to
green (GREEN) in the **same** commit, and never reduces the test count or skips a test to pass —
exactly what the gate verifies after the fact.

---

## Unit Test Conventions

### Naming

```python
# Pattern: test_<unit>_<scenario>_<expected_outcome>
def test_hitl_gateway_timeout_returns_rejected() -> None: ...
def test_pii_filter_email_is_masked() -> None: ...
def test_risk_scorer_empty_action_type_raises_value_error() -> None: ...
```

### AAA Structure

```python
def test_feedback_loop_high_rejection_rate_increases_bias() -> None:
    # Arrange
    stats = ActionStats(action_type="execute_code", total=100, rejections=60, approvals=40)

    # Act
    adjustment = compute_bias_adjustment(stats, threshold=0.5)

    # Assert
    assert adjustment.delta > 0
    assert adjustment.action_type == "execute_code"
```

### Fixtures

Shared fixtures live in `tests/fixtures/`. Keep them **synthetic** — no real PII ever.

```python
# tests/fixtures/requests.py
import pytest
from src.agents.hitl_gateway import PendingAction

@pytest.fixture
def low_risk_action() -> PendingAction:
    return PendingAction(
        agent_id="test-agent-00000000",
        action_type="read_file",
        payload={"path": "/tmp/test.txt"},
        correlation_id="00000000-0000-0000-0000-000000000001",
    )
```

---

## Integration Test Conventions

Integration tests use a dedicated Docker Compose stack on offset ports (see `docker-compose.test.yml`).

```bash
make test-infra-up    # start test stack (offset ports to avoid conflict with dev stack)
make test-python      # run unit + integration
make test-infra-down
```

**What belongs in integration tests:**

- Redis store round-trips (HITLRedisStore, RedisRequestStore)
- Kafka publish/consume cycles
- Alembic migration correctness
- OTel trace propagation across service boundaries

**What does NOT belong in integration tests:**

- Business logic (that's unit territory)
- UI flows (that's E2E)
- Inter-service REST contracts (that's Pact contract tests)

---

## Contract Tests (Pact)

Contract tests verify the API contract between a consumer (e.g., frontend) and a provider (e.g., api-gateway) without running both services simultaneously.

```
tests/contract/
├── pacts/                         # Generated Pact JSON files (checked in)
└── test_harness_contracts.py      # In-process schema contracts for agent harness
```

**When to write a contract test:**

- Any time a new REST endpoint is added that a frontend or other service will consume
- When changing the shape of an existing response that has a downstream consumer

See Wave 6 for REST Pact expansion.

---

## Security Tests

Security tests live in `tests/security/` and cover:

| Test file                        | What it validates                                          |
| -------------------------------- | ---------------------------------------------------------- |
| `test_pii_leakage.py`            | PII is masked before log writes, LLM calls, broker publish |
| `test_prompt_injection.py`       | Injection guard rejects known attack patterns              |
| `test_guardrails_integration.py` | End-to-end guardrail pipeline (PII → injection → audit)    |
| `test_owasp_llm.py`              | OWASP LLM Top 10 coverage                                  |

Run security tests: `make test-security-python`

---

## Chaos Tests

Chaos experiments test resilience under failure. They are defined as YAML manifests in `tests/chaos/experiments/` and the game-day playbook is in `tests/chaos/runbooks/game-day-playbook.md`.

```bash
# Run a specific chaos experiment
uv run pytest tests/chaos/ -m chaos -k "broker_outage" -v
```

**Existing experiments:**

- `broker-outage.yaml` — Kafka unavailable → InMemoryBroker fallback
- `hitl-store-degradation.yaml` — Redis degraded → InMemoryHITLStore
- `llm-api-timeout.yaml` — LLM API times out → circuit breaker opens
- `prompt-injection-under-load.yaml` — injection attempts at high concurrency

---

## Mutation Testing (Recommended, Not Gated)

Mutation testing verifies that your tests actually catch bugs, not just achieve line coverage.

```bash
uv run mutmut run --paths-to-mutate src/agents/hitl_gateway.py
uv run mutmut results
```

A mutation score > 70% for critical modules (`hitl_gateway.py`, `pii_filter.py`, `risk_scorer.py`) is the target. Mutation testing is not a CI gate but should be run before major releases.

---

## Running Specific Tests

```bash
# Single file
uv run pytest tests/unit/agents/test_hitl_gateway.py -q

# Single test function
uv run pytest tests/unit/agents/test_hitl_gateway.py::test_timeout_returns_rejected -q

# All unit tests with coverage
uv run pytest tests/unit/ --cov=src --cov-report=term-missing -q

# All tests including integration (requires make test-infra-up first)
make test-python
```
