# ADR-0051: Model Behavioral Contracts

**Status:** Accepted
**Date:** 2026-06-06
**Deciders:** AI Governance Lead, Security Lead
**Refs:** Issue #36, secure-by-design-agentic-ai-compliance-v2.md §MLSecOps (ML1)

---

## Context

The four secure-by-design pillars (Waves 21–24) protect the system against guardrail
regressions, tool misuse, runtime policy violations, and adversarial inputs. However,
one gap remained: **model behavioral drift** — the risk that an LLM model update silently
changes how the model responds to refusal prompts, spec constraints, or PII-exposure requests.

Behavioral drift is distinct from guardrail regression:

- Guardrail regressions are caught by `tests/abuse_cases/` (ADR-0050), which mock the LLM.
- Behavioral drift can only be detected by making real API calls to the model.

Without a versioned contract and a path-triggered test suite, a model provider could ship
a model update that weakens refusal behavior or starts reproducing PII — and the repository
would not detect it until a production incident.

---

## Decision

### ML1 — Model Behavioral Contract (`docs/dependency-manifest.yaml`)

Every LLM model entry in `docs/dependency-manifest.yaml` gains three new fields:

| Field                         | Type              | Purpose                                                                 |
| ----------------------------- | ----------------- | ----------------------------------------------------------------------- |
| `behavioral_contract_version` | string            | Semantic version of the behavioral contract spec the model must satisfy |
| `last_contract_tested`        | date (YYYY-MM-DD) | Date the model was last verified against the contract suite             |
| `contract_test_suite`         | path              | Path to the test suite that verifies the contract                       |

When `behavioral_contract_version` is bumped (e.g. new prohibited behavior added), the
model **must** be re-tested against the new contract before merge.

### ML1 — Contract Test Suite (`tests/model_contract/`)

Three test files, each with `@pytest.mark.model_contract`:

| File                       | Contract area                                                        | Real API calls |
| -------------------------- | -------------------------------------------------------------------- | -------------- |
| `test_refusal_behavior.py` | Model refuses jailbreaks, authority overrides, credential extraction | Yes            |
| `test_spec_adherence.py`   | Model respects `[SPEC_CONTRACT]` allowed/prohibited boundaries       | Yes            |
| `test_pii_non_leakage.py`  | Model does not echo, reproduce, or infer PII from masked context     | Yes            |

All tests skip automatically when `ANTHROPIC_API_KEY` is not set, so normal CI runs
are unaffected. Synthetic (fake) PII is used — no real personal data in any test.

### ML1 — Path-Triggered CI Workflow (`.github/workflows/ci-model-contract.yml`)

Runs only on PRs that touch:

- `docs/dependency-manifest.yaml`
- `specs/ai/**`
- `tests/model_contract/**`

This ensures the contract is re-verified whenever a model is upgraded, a new behavioral
requirement is added to the spec, or the test suite itself is modified.

The workflow also supports manual dispatch with a `model_id` input, enabling pre-promotion
testing of a new model version before `dependency-manifest.yaml` is updated.

---

## Alternatives Considered

- **Embed contract tests in `tests/security/`** — rejected because contract tests make
  real API calls and must be path-filtered to avoid burning API budget on every PR.
  Security tests use mocks and run on every commit.
- **Run contract tests on a schedule** — considered for weekly drift detection. Deferred;
  path-triggered testing covers the highest-risk moments (model upgrades, spec changes).
  A scheduled job can be added later without changing this ADR.
- **Use model evals framework** — out of scope for this template; the three-file test
  structure is intentionally lightweight and wraps the existing pytest infrastructure.

---

## Consequences

### Positive

- **Behavioral drift detected before production**: contract tests run on model upgrade PRs,
  not only after deploy.
- **Versioned contracts**: `behavioral_contract_version` in `dependency-manifest.yaml`
  makes the "which behaviors are promised" question answerable for auditors.
- **Zero cost in normal CI**: `model_contract` marker tests are skipped when no API key,
  so no accidental budget burn in developer or standard PR runs.

### Negative / Trade-offs

- **Real API cost**: each contract test run consumes ~5 000 input + 2 500 output tokens
  across all three files. At current Anthropic pricing this is negligible but must be
  tracked against the monthly budget in `dependency-manifest.yaml`.
- **Network dependency**: contract tests fail if the Anthropic API is unreachable. The
  `--timeout=60` guard prevents indefinite hangs.
- **Maintenance burden**: when the model provider updates refusal behavior (expected
  positive change), contract tests must be reviewed to avoid false failures.
