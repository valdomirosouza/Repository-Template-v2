# ADR-0066 — SPEC-LGS-001 Runtime Stack: Java 21 / Spring Boot (override of NFR-02)

**Status:** Accepted
**Date:** 2026-06-11
**Authors:** Valdomiro Souza
**Reviewers:** Tech Lead
**Relates to:** [ADR-0025](ADR-0025-language-selection.md) (Language Selection — override clause), [ADR-0003](ADR-0003-async-api-strategy.md) (async strategy), [ADR-0012](ADR-0012-pii-masking-strategy.md) (PII)
**Scope:** `SPEC-LGS-001` (Log-Based Golden Signals) only — does **not** change the platform default.

---

## Context

`SPEC-LGS-001` (Log-Based Golden Signals) specifies a containerised pipeline that ingests
HAProxy access logs, extracts the four Golden Signals, aggregates them into time windows, and
exposes latency percentiles over a REST API. Its **NFR-02** mandates _"Python asyncio-native
throughout (FastAPI for APIs, async worker). Pin Python to the repo's supported runtime."_

A `/deliver` run was commissioned with `LANGUAGE=JAVA`, which **conflicts** with NFR-02. The
governed delivery (DRY-RUN, GOVERNED tier) surfaced this as a tracked, merge-blocking deviation
**`SPEC-DEV-LANG`** (see `reports/SPEC-LGS-001-log-based-golden-signals/FINAL-REPORT.md` §0/§5,
action AI-01). CLAUDE.md §3.6 (grounding & non-fabrication) and §7 (PR checklist) require every
`SPEC_DEVIATION` to map to a tracked decision — an ADR or a spec amendment — before any code is
written. This ADR is that decision.

[ADR-0025](ADR-0025-language-selection.md) already governs language choice via a workload
decision matrix **and an explicit Overrides clause**: a service may deviate from the matrix when
(1) the deviation is justified referencing ADR-0025, (2) the Tech Lead approves, and (3) the
service still satisfies guardrail, observability, and HITL requirements in its chosen language.
This ADR invokes that override clause for `SPEC-LGS-001` rather than superseding ADR-0025.

**Honest read of the ADR-0025 matrix for this workload.** The pipeline has two characters:

- as an _ingestion / high-throughput data pipeline_ the matrix leans **Python** (data pipelines)
  or **Go** (high-throughput event workers);
- as _complex domain logic_ (windowing, rank-based percentile interpolation, signal extraction,
  retention) the matrix row "complex domain logic / DDD-heavy" recommends **Java (Spring Boot)**.

So Java is a **defensible-but-non-default** choice that legitimately requires this documented
override. We record it as such — not as the matrix's first recommendation.

## Decision

**Implement the `SPEC-LGS-001` services in Java 21 / Spring Boot 3.4.5**, overriding NFR-02's
Python/FastAPI mandate for this feature only, under the ADR-0025 override clause.

1. **Runtime:** Java 21 (matching the repo's pinned `java.version=21` in `services/*/pom.xml`
   and `JAVA_VERSION: "21"` in `.github/workflows/ci-java.yml`), Spring Boot 3.4.5 (the version
   already used by `services/domain-service`).
2. **Asyncio-equivalence (the heart of NFR-02's intent).** NFR-02 asked for _asyncio-native_
   concurrency to decouple ingestion from processing. Java 21 **virtual threads (Project Loom)**
   provide the equivalent non-blocking, high-concurrency model; the async ingestion→queue→worker
   decoupling required by FR-04/FR-05 is satisfied with virtual-thread executors (aligned with
   ADR-0003's async strategy — Redis Streams remains rejected _as a queue_; see the delivery's
   ADR-0068 draft). NFR-02 is therefore **amended in intent-preserving form**, not dropped.
3. **Guardrail / observability / HITL parity (ADR-0025 condition 3).** Because the Python-native
   guardrail library (`src/guardrails/`) is not reachable in-process from a Java service
   (ADR-0025 Consequences), this service **must** reimplement the equivalent controls in Java:
   - **PII masking (FR-02, ADR-0012):** IPv4 last-octet / IPv6 last-80-bit masking implemented in
     the Java ingestion path _before_ any persist or log — parity with `pii_filter.py`.
   - **Audit immutability (FR-14, ADR-0026):** immutable audit trail in the Java service.
   - **Observability (NFR-03, ADR-0043–0046):** OTel via the OpenTelemetry Java agent +
     Micrometer/Prometheus, structured JSON logs, `X-Trace-Id` propagation — per the Java backend
     quickstart, not the Python instrumentation.
   - **HITL/HOTL metadata (FR-12/13, ADR-0011):** the `_governance` block + threshold flip are
     response metadata emitted by the Java analytics API; no change to the runtime HITL gateway.
4. **Scope of the override:** `SPEC-LGS-001` only. The platform default (ADR-0025 matrix) is
   unchanged; the active core remains Python/FastAPI.

## Consequences

### Positive

- Resolves `SPEC-DEV-LANG`: the spec and the chosen stack are now consistent and traceable; a
  future `/deliver code java governed …` run is spec-conformant and will not stop at Phase 4.
- Reuses the repo's existing, instrumented Java toolchain: `ci-java.yml`, `make lint-java`
  (Checkstyle + SpotBugs + OWASP dependency-check), `make test-unit-java`, Spring Boot 3.4.5.
- Java 21 virtual threads preserve NFR-02's concurrency intent without the asyncio runtime.

### Negative / Trade-offs

- **Guardrail re-implementation cost & risk.** PII masking and audit immutability must be rebuilt
  and _independently tested_ in Java; they no longer inherit `src/guardrails/` coverage. This is
  the principal risk and is why DevSecOps (Phase 9) + abuse-case tests (Phase 8) are mandatory.
- **Diverges from the matrix's first recommendation** (Python/Go for an ingestion pipeline);
  accepted as a documented override, not a silent default.
- **Polyglot operational surface** grows (another Spring Boot service to run, scan, and operate).

### Neutral

- Docker Compose / containerisation (NFR-01) and the REST contract (§8) are language-agnostic and
  unchanged.
- The two delivery-drafted ADRs (Redis-as-time-series-store, Golden-Signal-extraction-rules) and
  the queue ADR are authored at real implementation time; their numbers are assigned then (this
  ADR took 0066).

## Alternatives Considered

- **Keep Python/FastAPI (no override)** — the matrix-aligned default for a data pipeline; rejected
  per the owner's decision to standardise this service on the Java/Spring Boot domain stack.
- **Amend NFR-02 only, without an ADR** — rejected: ADR-0025's override clause requires a
  _referenced, Tech-Lead-approved justification_, and a binding decision record is the auditable
  form of that (CLAUDE.md §3.4, §7).
- **Go** — strong for the high-throughput worker, but weaker fit for the percentile/windowing
  domain logic and not requested; not chosen.

## References

- `specs/system/SPEC-LGS-001-log-based-golden-signals.md` — NFR-02 (amended to reference this ADR)
- [ADR-0025](ADR-0025-language-selection.md) — Language Selection (override clause invoked)
- [ADR-0003](ADR-0003-async-api-strategy.md) · [ADR-0012](ADR-0012-pii-masking-strategy.md) · ADR-0043–0046 (observability) · [ADR-0011](ADR-0011-hitl-hotl-model.md) · [ADR-0026](ADR-0026-sox-audit-log-immutability.md)
- `reports/SPEC-LGS-001-log-based-golden-signals/FINAL-REPORT.md` — SPEC-DEV-LANG, action AI-01
