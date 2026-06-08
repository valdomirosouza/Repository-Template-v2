# Delivery Plan — SPEC-LGS-001 Log-Based Golden Signals

- **Mode:** `DRY-RUN` (governed simulation — no real side-effects; artefacts under `reports/<SLUG>/` only)
- **Spec:** `specs/system/SPEC-LGS-001-log-based-golden-signals.md` (status: `draft`)
- **SLUG:** `SPEC-LGS-001-log-based-golden-signals`
- **Run start:** 2026-06-08T11:51:32Z
- **Orchestrator:** `/deliver` skill → `phase-executor` subagent per phase (ADR-0058)

> ⚠️ **Governance note (dry-run finding):** the spec is `status: draft`, not `approved`.
> Per CLAUDE.md Pre-0e a real (CODE) run must not write product code until the spec is
> `approved` via Spec-as-PR. A DRY-RUN is permitted against a draft for planning/validation,
> but this is recorded as an open-HITL item.

## Problem summary

A governed, containerised pipeline that ingests HAProxy access logs, masks client IPs at the
boundary, extracts the four Golden Signals (traffic, latency, error, saturation) per
`(path, window)`, aggregates them into 1m/5m windows in a Redis time-series store, and serves
P50/P95/P99 percentiles + a `_governance` block over a REST API. It is the **data foundation**
an Agentic AI Copilot will consume to reduce MTTD/MTTR — the agent itself is out of scope.

## Risk class

**MEDIUM-HIGH.** Drivers:
- **Untrusted ingestion boundary** (`POST /ingestion` accepts external log batches) → STRIDE pass required (§11).
- **PII processing** (client IP, L-classified telemetry) → DPIA/RIPD review required (CLAUDE.md §3.1).
- **AuthN/abuse surface** (API-key auth, rate limiting) → OWASP A01/A07.
- **Immutable audit trail** (ADR-0026) → audit-integrity controls.
- New infra dependency (Redis as TSDB) → two new ADRs to author (§11).

## 15-phase plan — governing ADR(s) per phase

| Phase | Name | Governing ADR(s) / gate source | Dry-run focus |
|------|------|--------------------------------|---------------|
| 0 | Intake & Prioritization | ADR-0058 | this plan + backlog (done) |
| 1 | Conception | ADR-0058 | discovery note (problem/value/risk) |
| 2 | Discovery | ADR-0012, specs/privacy/ | NFR doc + **PII classification** (blocking) |
| 3 | Grooming | DoR checklist | feature-spec shell + DoR (8 criteria) |
| 4 | Specification | ADR-0058, governance.yml | spec completeness vs template §1–16 |
| 5 | Architecture | ADR-0003 (async), + 2 new ADRs (Redis-TSDB, GS-extraction) | ADR drafts + STRIDE |
| 6 | Development | code-check.yml | simulate impl; evidence = `make lint-python`, `make test-unit-python` |
| 7 | Code Review | pr-governance, governance-gate, ci-ai-review | DoD checklist (simulated PR) |
| 8 | Testing | test-unit/-integration/-security; coverage ≥80% | `make test-unit-python`, `make test-security-python` |
| 9 | Security & DevSecOps | ADR-0029 | `make check-control-bindings`, `make sbom` (report-only) |
| 10 | AI Safety & Agent Governance | ADR-0050/0051 (conditional) | **likely N/A** — see note below |
| 11 | Observability & Operational Readiness | ADR-0043–0046, probe-lint | `make smoke`/`make doctor`; OTel/probe check; PRR ≥90% |
| 12 | Release Candidate | ADR-0057 (version SoT) | version/CHANGELOG dry-check (simulate, no bump) |
| 13 | Production Deployment | ADR-0027 (CAB), deploy-rollback | **simulate** canary plan — never deploy |
| 14 | Post-Deployment & Learn | ADR-0028 (DORA) | retrospective stub; DORA placeholders |

### Phase 10 conditionality

The spec adds a `_governance` block and an FR-13 HITL-flip, which are **governance-adjacent**,
but it modifies **no** `src/agents/` or `src/guardrails/` code and introduces **no** new
`action_type` or autonomy flag (the Copilot is explicitly out of scope). Tentative verdict:
**N/A** — to be confirmed by the Phase 10 executor. If a reviewer judges the HITL-recommendation
metadata to constitute an agent-governance surface, escalate to a real Phase 10 gate.

## Guardrails in scope (CLAUDE.md §3)

- **§3.1 Privacy:** `pii_filter.py` before any log write/LLM call; IP masking before persist (FR-02); DPIA/RIPD flag.
- **§3.2 Security:** input validation at the ingestion boundary; parameterized store access; TLS/`rediss://` in prod; API-key auth; OWASP A01/A03/A07/A09.
- **§3.4 Architecture:** no direct store access from API layer → go through a processing/worker layer; async event decoupling (queue) per ADR-0003.
- **§3.5 Quality:** unit coverage ≥80% on percentiles/masking/extraction; CHANGELOG updated.

## Dry-run evidence strategy

Evidence = the repo's **own** read-only validation targets, tee'd into `reports/<SLUG>/logs/`:
`make lint-python`, `make test-unit-python`, `make test-security-python`,
`make check-control-bindings`, `make smoke`/`make doctor`. **No** deploy/release/rollback/
flag-change targets are invoked. Every gate that would need a real human is auto-approved and
logged (`HITL: auto-approved (dry-run)`) and listed in the FINAL-REPORT open-HITL section.

## Open-HITL items anticipated (real human needed in a CODE run)

1. **Spec approval** — move `draft → approved` via Spec-as-PR before any code (Phase 4).
2. **DPIA/RIPD review** — new PII (client IP) processing (Phase 2, DPO).
3. **Two new ADRs** — Redis-as-TSDB + Golden-Signal extraction rules (Phase 5, Tech Lead).
4. **Security sign-off** — STRIDE over the ingestion boundary (Phase 9, Security Lead).
5. **CAB approval + deploy** — production promotion is human-gated (Phase 13).
