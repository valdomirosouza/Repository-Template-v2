# ADR-0072 — Versioned Security Control Matrices (OWASP ASVS v5.0.0 + GenAI/LLM)

**Status:** Accepted
**Date:** 2026-06-12
**Authors:** Valdomiro Souza
**Milestone:** v2.16.0 — Governance Enforcement Hardening (Track B)
**Relates to:** [ADR-0029](ADR-0029-devsecops-pipeline-security.md) (DevSecOps), [ADR-0061](ADR-0061-control-binding-ci-gate.md) (control-binding gate), [ADR-0045](ADR-0045-genai-semantic-conventions.md) (GenAI conventions)

---

## Context

The repository asserts conformance to **OWASP Top 10** and **OWASP LLM Top 10** in prose
(`CLAUDE.md §3.2`), but the claims are not machine-verifiable: there is no artifact mapping each
control to the code that implements it, the test that verifies it, and the CI gate that enforces
it. Generic "OWASP Top 10" language also lets an agent reason loosely ("we cover injection")
rather than from a pinned standard to a specific spec, test, and gate.

For enterprise-grade secure development, security evidence must be **auditable** and **anti-rot**:
a control claim that references a deleted file or a non-existent CI job is worse than no claim — it
is a false assurance (CLAUDE.md §3.6, no fabricated control claims).

## Decision

Security claims map to **pinned standard versions** via machine-readable matrices, schema-validated
by the control-binding gate.

1. **ASVS matrix:** `specs/security/asvs-control-matrix.yaml` — entries keyed by
   `asvs: v5.0.0-<chapter.section.req>` (OWASP ASVS **5.0.0**, the current stable release).
2. **GenAI/LLM matrix:** `specs/security/owasp-genai-control-matrix.yaml` — the LLM/agentic
   controls (prompt injection, insecure output handling, sensitive-info disclosure, excessive
   agency → the F7 high-risk guard + HITL/HOTL boundaries, overreliance), with the **taxonomy
   version pinned explicitly** (LLM risk taxonomies evolve fast).
3. **Entry schema** (`specs/security/schemas/control-matrix.schema.json`): each entry carries
   `control`, `implemented_by: [paths]`, `verified_by: [test paths + CI job ids]`, `gate:
[required-check names]`, `owner`, and `status: implemented | partial | n/a`.
4. **Anti-rot + anti-fabrication validation** (`scripts/governance/check_control_matrix.py`,
   extending the `check_control_bindings.py` pattern, wired into the governance gate):
   - a `implemented_by`/`verified_by` path that does not exist **fails CI** (dead-reference rot);
   - an `n/a` entry **without a justification fails CI** (CLAUDE.md §3.6, no fabricated coverage).

## Consequences

### Positive

- OWASP conformance becomes auditable: an auditor (or an agent) traces standard → code → test →
  gate from one file.
- Dead-reference + unjustified-`n/a` failures keep the matrices honest as the code evolves.
- Pinned versions make "which OWASP we follow" explicit and updatable as a tracked decision.

### Negative / Trade-offs

- Authoring + maintaining the matrices is real effort; the validator amortises it by failing fast
  on rot rather than letting the matrix silently drift out of truth.

### Neutral

- The matrices are starting evidence sets for the template; adopters extend them for their own
  controls. They do not replace the per-control `verified_by` tests — they index them.

## Alternatives Considered

- **Keep prose-only OWASP references** — rejected: not auditable, lets coverage claims drift.
- **Make the control-binding gate validate full compliance correctness** — rejected (ADR-0061
  scopes it to _declaration discipline_; correctness lives in the `verified_by` tests). Putting
  full correctness here would make the gate brittle and slow.

## References

- `improvements-2026-06-12-2021.md` backlog P1 #3/#4 · `reports/STRENGTHENING-PLAN.md` W2-2
- `governance-enforcement-hardening-v1.0.0.md` W2-T1/T2 (ADR-0068-as-proposed → renumbered 0072)
- OWASP ASVS: <https://owasp.org/www-project-application-security-verification-standard/>
- OWASP LLM Top 10: <https://owasp.org/www-project-top-10-for-large-language-model-applications/>
