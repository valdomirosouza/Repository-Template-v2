# Tests

This directory contains all automated tests for the system. Tests are organised by type.

---

## Test Types

| Directory            | Type                                  | Runner                  | When it runs              |
| -------------------- | ------------------------------------- | ----------------------- | ------------------------- |
| `tests/unit/`        | Unit tests                            | pytest                  | Every PR (CI gate)        |
| `tests/integration/` | Integration tests                     | pytest + docker-compose | Every PR after unit tests |
| `tests/security/`    | Security tests (SAST, PII, OWASP LLM) | pytest                  | Every PR (blocking gate)  |
| `tests/e2e/`         | End-to-end tests                      | pytest                  | Staging gate only         |
| `tests/contract/`    | Contract tests (Pact)                 | pytest                  | Every PR                  |
| `tests/performance/` | Load and benchmark tests              | k6 / pytest-benchmark   | Staging gate only         |
| `tests/chaos/`       | Chaos engineering experiments         | Litmus / Chaos Toolkit  | Weekly scheduled game day |

---

## Running Tests Locally

```bash
# All unit tests with coverage
make test-unit

# Security tests only
make test-security

# All tests (unit + integration)
make test

# Single test file
uv run pytest tests/unit/guardrails/test_pii_filter.py -v
```

---

## Coverage Requirements

- Unit test coverage: **≥ 80%** (enforced as CI gate — see `harness/code-check.yml`)
- Security tests: **100% pass rate** (zero findings allowed)
- Branch coverage on all guardrail decision paths: **100%**

---

## Synthetic Data Policy

All test files must use clearly synthetic, obviously fake data. Real PII in any test file is a **P1 security incident**.

| PII type   | Required synthetic value                 |
| ---------- | ---------------------------------------- |
| CPF        | `000.000.000-00`                         |
| Email      | `fake@example.com` or `test@example.com` |
| IP address | `192.0.2.1` (RFC 5737 TEST-NET)          |
| Phone      | `+00 00 00000-0000`                      |
| User ID    | `00000000-0000-0000-0000-000000000000`   |

Prompt injection test inputs must use placeholder tokens: `SYNTHETIC_INJECT_ATTEMPT`, `SYNTHETIC_OVERRIDE_TOKEN`, `TEST_JAILBREAK_PATTERN`. Never use real exploit strings.

---

## Key Test Files

| File                                                   | What it tests                                                    |
| ------------------------------------------------------ | ---------------------------------------------------------------- |
| `tests/unit/guardrails/test_pii_filter.py`             | PII detection and masking (all 8 categories)                     |
| `tests/unit/guardrails/test_prompt_injection_guard.py` | Structural anomaly detection                                     |
| `tests/security/test_owasp_llm_top10.py`               | OWASP LLM Top 10 guardrail coverage (LLM01, LLM06, LLM08, LLM09) |
| `tests/security/test_pii_leakage.py`                   | End-to-end PII leakage prevention                                |
| `tests/chaos/runbooks/game-day-playbook.md`            | Chaos game day procedure                                         |

---

## Adding New Tests

1. Place tests in the appropriate subdirectory based on type
2. Use synthetic data only (see policy above)
3. Ensure coverage does not drop below 80% after your addition
4. Security test additions require Security Lead review (see `.github/CODEOWNERS`)
