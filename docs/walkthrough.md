# Worked Walkthrough — one feature, end to end (SPEC-LGS-001)

> **This is the canonical worked example** of the 15-phase Agentic Spec-Driven Delivery
> Workflow (ADR-0058). It narrates **one real feature** — the **Log-Based Golden Signals**
> service (SPEC-LGS-001) — from a raw idea through discovery, spec, ADRs, code, evaluation,
> canary, and SLO. Every link below points at a **real artefact already in this repository**,
> so you can read the actual document each phase produced rather than a hypothetical one.

**Feature:** a Java 21 / Spring Boot service that ingests HAProxy access logs and computes the
four Golden Signals (Traffic, Errors, Saturation, Latency) into queryable 1m/5m windows for an
agent-facing analytics read path.

**How to read this:** each phase is one or two sentences plus a link to the artefact it owes.
The artefacts are genuine — they were produced by a governed `/deliver dry-run` over this spec
(see the [delivery example](sdlc/deliver-example/README.md)), so the lifecycle below is a record
of what actually happened, not a script.

---

## The lifecycle at a glance

```
Intake → Conception → Discovery → Grooming → Specification → Architecture
   → Development → Code Review → Testing → DevSecOps → AI Safety
   → Observability → Release RC → Production (canary) → Post-Deploy (SLO/DORA)
```

Risk-based: low-risk changes take a short path; only high-impact / AI / security / infra changes
pass every gate. SPEC-LGS-001 ran at **tier GOVERNED**. Canonical model:
[`sdlc/agentic-spec-driven-delivery.md`](sdlc/agentic-spec-driven-delivery.md). Full phase
lifecycle: [`process/WORKFLOW.md`](process/WORKFLOW.md).

---

## Phase 0–1 — Intake & Conception

The idea ("compute Golden Signals from access logs for the analytics path") is triaged for
problem, value, and risk class, then turned into a tracked plan and backlog before any code.

- Plan & backlog: [`sdlc/deliver-example/00-plan.md`](sdlc/deliver-example/00-plan.md) ·
  [`sdlc/deliver-example/backlog.yaml`](sdlc/deliver-example/backlog.yaml)

## Phase 2 — Discovery

The feature's NFRs and PII classification are settled and reviewed via **Spec-as-PR** (not the
runtime HITL gateway). Discovery artefacts follow the package convention in
[`product/README.md`](product/README.md).

- Governance model: [`process/HITL-GOVERNANCE.md`](process/HITL-GOVERNANCE.md)

## Phase 3 — Grooming

The Definition of Ready is checked before the work can enter a sprint — for SPEC-LGS-001 the
dry-run correctly recorded DoR as **not yet met** while the spec was still `draft`.

- Gate: [`process/DEFINITION_OF_READY.md`](process/DEFINITION_OF_READY.md)

## Phase 4 — Specification

The system spec and the implementable feature spec leave **no ambiguity** for the build: every
component, key grammar, threshold, edge case, and test is pinned. This is the contract Phase 6
depends on.

- System spec: [`../specs/system/SPEC-LGS-001-log-based-golden-signals.md`](../specs/system/SPEC-LGS-001-log-based-golden-signals.md)
- Feature spec: [`../specs/features/SPEC-LGS-001-golden-signals-feature-spec.md`](../specs/features/SPEC-LGS-001-golden-signals-feature-spec.md)

## Phase 5 — Architecture (ADRs + threat model)

Four ADRs capture the binding architectural decisions, and a threat model covers the security
surface of an externally-fed ingestion endpoint.

- [ADR-0066 — runtime stack: Java 21 / Spring Boot](adr/ADR-0066-spec-lgs-001-runtime-stack-java-spring-boot.md)
- [ADR-0067 — Redis as the time-series store](adr/ADR-0067-redis-as-timeseries-store.md)
- [ADR-0068 — Golden-Signal extraction rules](adr/ADR-0068-golden-signal-extraction-rules.md)
- [ADR-0069 — bounded in-JVM virtual-thread queue](adr/ADR-0069-queue-implementation.md)
- Threat model: [`../specs/security/threat-model-SPEC-LGS-001-golden-signals.md`](../specs/security/threat-model-SPEC-LGS-001-golden-signals.md)

## Phase 6 — Development

The approved spec is implemented as the single Spring Boot service `services/golden-signals`,
with the four logical components decoupled by the bounded queue from ADR-0069.

- Service: [`../services/golden-signals/pom.xml`](../services/golden-signals/pom.xml) ·
  [`GoldenSignalsApplication.java`](../services/golden-signals/src/main/java/com/yourorg/goldensignals/GoldenSignalsApplication.java)
- Ingestion API: [`IngestionController.java`](../services/golden-signals/src/main/java/com/yourorg/goldensignals/api/IngestionController.java) ·
  Analytics API: [`AnalyticsController.java`](../services/golden-signals/src/main/java/com/yourorg/goldensignals/api/AnalyticsController.java)
- Aggregation worker: [`AggregationWorker.java`](../services/golden-signals/src/main/java/com/yourorg/goldensignals/queue/AggregationWorker.java)

## Phase 7 — Code Review

The PR is opened, the Definition of Done is verified, and **at least one human approval** is
required before merge — never waived by the agent.

- Gate: [`process/DEFINITION_OF_DONE.md`](process/DEFINITION_OF_DONE.md)

## Phase 8 — Testing (evaluation)

The quantity gate (≥80% coverage) and the integrity gate both apply. The dry-run produced real,
green evidence on the tree.

- Tests live alongside the service under `services/golden-signals/src/test/`.
- Evidence (see FINAL-REPORT below): **945 unit tests · 86.56% coverage · 39 security tests** pass.

## Phase 9 — DevSecOps

SAST, SCA, container scan, SBOM, and DAST run; promotion waits on **Security-Lead sign-off** and
a cosign attestation — an outward human/CI gate that the dry-run correctly left BLOCKED.

## Phase 10 — AI Safety (conditional)

This phase fires only for AI/agent changes. SPEC-LGS-001 touches no `src/agents/` or
`src/guardrails/` code, so it was correctly **N/A** for this feature.

## Phase 11 — Observability & PRR

OTel spans, Prometheus metrics, dashboards, and alert rules are verified, then PRR is signed off.

- Dashboard: [`../infrastructure/monitoring/grafana/dashboards/golden-signals.json`](../infrastructure/monitoring/grafana/dashboards/golden-signals.json)
- Alert rules: [`../infrastructure/monitoring/prometheus/rules/golden-signals.yaml`](../infrastructure/monitoring/prometheus/rules/golden-signals.yaml)

## Phase 12 — Release Candidate

The Definition of Release is checked, version is bumped, and dual `rc-approved` sign-off is
required — prepare-and-recommend only; a human applies the label.

- Gate: [`process/DEFINITION_OF_RELEASE.md`](process/DEFINITION_OF_RELEASE.md)

## Phase 13 — Production (canary + SLO gate)

Rollout is canary 5% → 25% → 100%. The promotion gate is **not hard-coded** — it reads the
per-service SLO file at each step (ADR-0073), and a missing file fails the pipeline. Production
deploy is the canonical STOP: CAB + Release-Manager authorization.

- Canary thresholds (read by `cd-production.yml`): [`sre/slo/golden-signals.yaml`](sre/slo/golden-signals.yaml)
- 30-day SLO objectives: [`sre/slo/golden-signals-slo.yaml`](sre/slo/golden-signals-slo.yaml)
- Decision: [ADR-0073 — SLO-driven canary thresholds](adr/ADR-0073-slo-driven-canary-thresholds.md)

## Phase 14 — Post-Deploy (learning, SLO & DORA)

DORA metrics are collected and sprint + release retrospectives are created. The service's own
SLOs (availability, latency, aggregate freshness) become the ongoing health contract.

- SLO contract: [`sre/slo/golden-signals-slo.yaml`](sre/slo/golden-signals-slo.yaml)

---

## The whole run, in one report

The end-to-end record of this walkthrough — every phase, its gate verdict, requirement
traceability, per-phase timing, and the open-HITL list — is the delivery report:

- **[`sdlc/deliver-example/FINAL-REPORT.md`](sdlc/deliver-example/FINAL-REPORT.md)** — 15 phases,
  8 BLOCKED at human gates, 1 FAIL (DoR), 1 SIMULATED, 1 N/A (AI Safety), 4 PASS.
- Index of the example outputs: [`sdlc/deliver-example/README.md`](sdlc/deliver-example/README.md)

Every consequential, irreversible step resolved to a **human gate** rather than being
auto-performed — which is the whole point of the workflow.

## Now drive your own

Copy [`../specs/SPEC-TEMPLATE.md`](../specs/SPEC-TEMPLATE.md), fill every section to
`status: approved`, then run `/deliver` over it. Full guide:
[`quickstart/delivering-a-spec.md`](quickstart/delivering-a-spec.md).
