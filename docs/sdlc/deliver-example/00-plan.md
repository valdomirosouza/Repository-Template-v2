# Delivery Plan — SPEC-LGS-001 (Log-Based Golden Signals)

> **Mode:** DRY-RUN (no real side-effects) · **Orchestrator:** /deliver · **Generated:** 2026-06-07
> **Spec:** `specs/system/SPEC-LGS-001-log-based-golden-signals.md` (status: draft)

## Problem summary
A governed, containerised pipeline that ingests HAProxy access logs, masks PII, extracts the
four Golden Signals per request path, aggregates them into 1m/5m windows, and exposes
P50/P95/P99 latency (+ traffic/error/saturation) over a REST API — the **data foundation** an
Agentic AI Copilot consumes to lower MTTD/MTTR under HITL/HOTL governance. The agent itself is
**out of scope** (Non-Goals §3).

## Risk class
**Normal feature, elevated** — new architecture (4 services + Redis + queue), **PII** (client-IP
masking, ADR-0012), **auth + rate-limiting** attack surface (threat model), immutable audit
(ADR-0026), and **two new ADRs required** (Redis-as-TSDB, Golden-Signal extraction rules).
**Not** an AI/agent change → Phase 10 (AI Safety) is **N/A**.

## 15-phase plan (governing ADRs per phase)
| Phase | Name | Governing ADR(s) | Dry-run focus |
| ----- | ---- | ---------------- | ------------- |
| 0 | Intake & Prioritization | ADR-0058 | this plan + backlog |
| 1 | Conception | ADR-0058 | problem/value/issue framing |
| 2 | Discovery | ADR-0012, privacy | discovery + NFR + PII classification (IP=L2) |
| 3 | Grooming | ADR-0058 | Definition of Ready check |
| 4 | Specification | ADR-0003 | spec completeness (FR/AC/contracts) |
| 5 | Architecture | ADR-0003, ADR-0020 | ADR drafts: Redis-TSDB + extraction rules |
| 6 | Development | ADR-0003, CLAUDE.md §3 | dev plan; lint baseline (`make lint-python`) |
| 7 | Code Review | CLAUDE.md §7 (DoD) | DoD checklist (dry-run, no PR) |
| 8 | Testing | NFR-05, ADR-0022 | coverage ≥80% (`make test-unit-python`) |
| 9 | Security & DevSecOps | ADR-0029 | `make check-control-bindings` + SBOM intent |
| 10 | AI Safety & Agent Governance | ADR-0058 | **N/A** — no agent surface |
| 11 | Observability & Operational Readiness | ADR-0004, golden-signals | `make doctor`; SLO/runbook intent |
| 12 | Release Candidate | ADR-0057 | DoR-Release (prepare-only) |
| 13 | Production Deployment | ADR-0027 | canary + rollback plan (human-executed) |
| 14 | Post-Deployment & Learn | ADR-0028 | DORA + retro template |

## Guardrails in scope
CLAUDE.md §3.1 PII (IP masking before persist/log — FR-02/AC-03), §3.2 security (auth, rate
limit, parameterized store access, SBOM), §3.4 architecture (async events — ADR-0003), §14
escalation. HITL gateway (ADR-0011) governs the analytics `_governance` block / HITL flip
(FR-13/AC-08).

## Dry-run evidence strategy
Run the repo's own validation targets on the current tree and tee to `logs/`:
`make lint-python` (Phase 6), `make test-unit-python` (Phase 8),
`make check-control-bindings` (Phase 9), `make doctor` (Phase 11). Phases that own
irreversible effects (12/13) are **prepare-and-recommend only**. No deploy/release/flag changes.

## HITL gate (Phase 0)
`HITL-GATE phase=0 reason="plan approval required before execution"` →
`HITL: auto-approved (dry-run)` — payload = this plan + backlog. (Real run would block for a human.)
