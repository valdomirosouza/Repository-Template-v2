# ADR-0050: Adversarial Abuse Testing Strategy

**Status:** Accepted
**Date:** 2026-06-06
**Deciders:** Security Lead, AI Governance Lead
**Refs:** Issue #35, secure-by-design-agentic-ai-compliance-v2.md §Pillar 4 (CV1, CV2, CV3)

---

## Context

Three continuous verification gaps existed:

- **CV1** — `tests/security/` covered OWASP LLM Top 10 and PII leakage, but no structured
  abuse-case library targeted agent-specific attack vectors: jailbreak, goal hijacking via
  tool responses, context overflow, multi-agent trust abuse, spec boundary violations.
- **CV2** — Adversarial tests that required real LLM API calls were expensive and therefore
  skipped in standard CI, running only pre-release. This created a window where newly
  introduced guardrail regressions would go undetected until release.
- **CV3** — The HITL gateway accepted any action payload structure. A hallucinated or injected
  payload with the wrong schema (missing fields, wrong types, oversized) could enter the HITL
  store or tool execution path unchecked.

---

## Decision

### CV1 + CV2 — `tests/abuse_cases/` directory

Five abuse case test files, each with the `@pytest.mark.abuse_case` marker:

| File                               | Attack vector tested                                           |
| ---------------------------------- | -------------------------------------------------------------- |
| `test_jailbreak_attempts.py`       | Instruction override, role switch, excessive length (LLM01/02) |
| `test_goal_hijacking.py`           | Poisoned tool responses, code-based goal hijacking             |
| `test_context_overflow.py`         | Context stuffing to push spec constraints out of scope         |
| `test_multiagent_trust_abuse.py`   | Planner→Generator context tampering (ContextSeal)              |
| `test_spec_boundary_violations.py` | Actions outside spec's allowed_action_types                    |

All tests use mock LLMs — no real API calls. This means:

- Zero cost per CI run
- Can run on every PR, not just pre-release
- No ANTHROPIC_API_KEY_CI required in the test environment

Added to `.github/workflows/ci.yml` `test-security` job:

```yaml
- name: Abuse case tests (continuous, mock-LLM)
  run: PYTHONPATH=. uv run pytest tests/abuse_cases/ -m abuse_case -q
```

The `abuse_case` marker is registered in `pyproject.toml`.

### CV3 — ActionSchemaValidator (`src/agents/action_schema_validator.py`)

- Loads YAML schema files from `infrastructure/agent-tools/action-schemas/`.
- Each schema declares `required` fields, `properties` with type annotations, and
  `max_payload_bytes` (default 10 KB).
- `validate(action_type, payload)` returns a `ValidationResult` with error list.
- `validate_or_raise(action_type, payload)` raises `ActionSchemaError` for use as a
  blocking gate in `HITLGateway.submit_for_approval()`.
- Unknown action_types (no schema registered) are allowed through with a debug log.
- Normalizes underscores → hyphens for schema lookup.

Three starter schemas ship in `infrastructure/agent-tools/action-schemas/`:

- `write-db-record.schema.yaml` (required: table, data)
- `send-email.schema.yaml` (required: to, subject, body)
- `execute-code.schema.yaml` (required: code, language; max 4 KB)

---

## Alternatives Considered

- **Real LLM abuse tests** — deferred to `tests/model_contract/` (Wave 25) which runs
  only on model-version-changing PRs. The abuse case tests validate guardrail behaviour,
  not model behaviour — mocks are the right tool.
- **jsonschema library** — considered for CV3 but not in the existing dependency set.
  The custom validator covers the required field/type checks with no new dependency.
  Full JSON Schema validation (patterns, minLength, etc.) can be added by importing
  `jsonschema` when needed.
- **Inline schema in tools.yaml** — embedding payload schemas in `tools.yaml` was
  considered but keeps concerns separate: `tools.yaml` = catalog metadata; `action-schemas/`
  = structural contracts.

---

## Consequences

- **Security +**: Guardrail regressions are now caught on every PR, not just pre-release.
- **CI runtime**: 58 abuse case tests run in < 0.1s (all mocks, no I/O).
- **Schema maintenance**: developers adding a new tool SHOULD add a corresponding schema
  file. Unknown action types pass through (permissive by default) to avoid blocking
  existing tools without schemas.
- **CLAUDE.md §3.2 update**: developers must run `make test-abuse-cases` before any PR
  touching `src/agents/` or `src/guardrails/`, and must not reduce the abuse case test count.
