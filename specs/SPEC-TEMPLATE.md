---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /deliver and CI read this block)
# Reuse: copy this file to specs/<domain>/<id-slug>.md, change id/title/owner,
# and rewrite each section. Keep the section skeleton — it maps 1:1 onto the
# 15-phase Agentic Spec-Driven Delivery workflow (ADR-0058) that `/deliver` drives.
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-XXX-000 # SPEC-<DOMAIN>-<NNN>; unique; used by /deliver as the SLUG base
title: <One-line feature title>
version: 0.1.0
status: draft # draft | in-review | approved | implemented | superseded
owner: <github-handle> # Product Owner or Tech Lead
created: YYYY-MM-DD
source: <origin — issue, RFC, research, customer request>
deployment_topology: monorepo-services # monorepo-services | standalone-repo  (decide in §1.4)
governing_adrs: [] # e.g. [ADR-0003, ADR-0011, ADR-0012] — reused, binding decisions
new_adrs_required: [] # short slugs for ADRs the Architecture phase must author
related_specs: [] # e.g. [specs/privacy/, specs/security/threat-model.md]
slo_ref: docs/sre/slo/slo.yaml # where this feature's SLOs are/were recorded
---

# SPEC-XXX-000 — <Title>

> **One-line scope.** <What this delivers, for whom, and the value — in one sentence.>

<!-- HOW TO USE THIS TEMPLATE
  • Every numbered section is mandatory. If a section truly does not apply, write
    "N/A — <reason>" — do not delete the heading.
  • Sections marked (gate) are checked by a phase gate in docs/process/gates/phase-gates.yaml.
  • Write code only after this spec reaches status: approved (CLAUDE.md §2; no code without a spec).
  • `/deliver specs/<domain>/<this-file>.md` drives the spec through all 15 phases as a
    governed dry-run and emits reports/<slug>/FINAL-REPORT.md. The map below shows which
    section feeds which phase — fill them well and the dry-run has real material to validate.
-->

## How `/deliver` reads this spec (section → phase)

| Spec section                                         | Feeds /deliver phase(s)                  | Gate it satisfies                                |
| ---------------------------------------------------- | ---------------------------------------- | ------------------------------------------------ |
| §1 Context, §2 Goals, §3 Non-Goals, §4 Consumers     | 0 Intake · 1 Conception                  | problem/value/risk recorded                      |
| §5 FR, §6 NFR                                        | 2 Discovery · 4 Specification            | discovery + nfr; FR→AC traceability              |
| §6 NFR (PII rows), §11 Governance/Privacy            | 2 Discovery · 9 Security & DevSecOps     | PII classification; threat & privacy review      |
| §7 Architecture, §14 ADR Impact, `new_adrs_required` | 5 Architecture                           | ADR(s) authored & accepted                       |
| §8 Interface Contracts (gate)                        | 4 Specification · 6 Development          | contract-driven dev (OpenAPI/AsyncAPI)           |
| §9 Data Model                                        | 6 Development · 9 Security               | schema validation; key/injection safety          |
| §10 Golden Signals & SLO (gate)                      | 11 Observability & Operational Readiness | SLOs + PRR                                       |
| §11 Governance/Privacy/Security (gate)               | 9 DevSecOps · 10 AI Safety (if agentic)  | STRIDE; AI-safety (conditional)                  |
| §12 Acceptance Criteria (gate)                       | 8 Testing · all phases                   | **becomes the dry-run evidence in FINAL-REPORT** |
| §13 Risks, §15 Open Questions                        | every phase boundary                     | surfaced as HITL items                           |

---

## 1. Context & Problem

### 1.1 Problem statement

<What problem, for whom, and the cost of not solving it.>

### 1.2 Research / product question

<The question this feature answers.>
### 1.3 Why now / motivation
<Why this is worth doing now.>
### 1.4 Deployment topology decision  *(decide before Phase 1)*
<`monorepo-services` (register in services.yaml, reuse CI/CD + governance) or `standalone-repo`. State the chosen value in the metadata header.>

## 2. Goals & Success Metrics

<!-- Goals MUST be measurable. If you cannot state a measure, it is a non-goal or an open question. -->

| ID   | Goal | Measure of success |
| ---- | ---- | ------------------ |
| G-01 |      |                    |

## 3. Non-Goals / Out of Scope

- <Explicitly what this does NOT do, to bound scope.>

## 4. Consumers & Personas

| Consumer | Need from this system |
| -------- | --------------------- |
|          |                       |

## 5. Functional Requirements

<!-- One testable statement per row, phrased EARS-style: "WHEN <trigger/condition>, the system
     SHALL <observable response>." (For ubiquitous behaviour: "The system SHALL <response>.")
     Each FR MUST trace to an acceptance criterion in §12 — see the coverage footer there. -->

| ID    | Requirement (EARS: WHEN … the system SHALL …) |
| ----- | --------------------------------------------- |
| FR-01 |                                               |

## 6. Non-Functional Requirements

<!-- Cover: containerisation, runtime, logging/trace, config-via-env, coverage ≥80% (CLAUDE.md §3.5),
     error handling, performance budget, pinned deps + SBOM. Flag any PII field here.
     Classify each NFR by the taxonomy in docs/product/nfr-taxonomy.md (category + evidence/gate). -->

| ID     | Requirement |
| ------ | ----------- |
| NFR-01 |             |

> Classify each NFR by the taxonomy in `docs/product/nfr-taxonomy.md` — pick a category and point
> at the evidence/gate it maps to (SLO, control matrix, PII classification, coverage, …).

## 7. Architecture

<Components, layers, data/event flow (ASCII diagram welcome). Align async flows with ADR-0003;
record any deviation as a new ADR in `new_adrs_required`.>

## 8. Interface Contracts _(gate: contract-driven dev)_

<!-- Source for the OpenAPI/AsyncAPI spec in docs/api/. Never hand-write stubs — generate from here. -->

| Method | Path | Auth | Purpose | Success | Errors |
| ------ | ---- | ---- | ------- | ------- | ------ |
|        |      |      |         |         |        |

## 9. Data Model

### 9.1 Entities / payloads (validated at boundaries)

### 9.2 Storage key/schema convention _(define once; all readers/writers must agree)_

### 9.3 Retention

### 9.4 Governance/response metadata (if applicable)

## 10. Golden Signals & SLO Definitions _(gate: observability)_

| Signal     | Derivation | Exposed as      |
| ---------- | ---------- | --------------- |
| Traffic    |            |                 |
| Latency    |            | P50 / P95 / P99 |
| Error      |            | error_rate      |
| Saturation |            |                 |

<Define this feature's SLOs in `docs/sre/slo/slo.yaml` and any thresholds that flip a response to HITL.>

## 11. Governance, Privacy & Security _(gate: threat & privacy review)_

| Concern                                  | Control in this spec | Maps to                        |
| ---------------------------------------- | -------------------- | ------------------------------ |
| Human oversight (HITL/HOTL)              |                      | ADR-0011                       |
| PII (classify L1–L4; mask at boundaries) |                      | ADR-0012, specs/privacy/       |
| Auditability (immutable trail)           |                      | ADR-0026                       |
| Authn / abuse (auth, rate limit)         |                      | specs/security/threat-model.md |
| Cost envelope                            |                      | ADR-0020                       |
| Pipeline security (SAST/SCA/secret/SBOM) |                      | ADR-0029                       |

<Run a STRIDE pass over every untrusted-input boundary. If the change touches `src/agents/`,
`src/guardrails/`, a new `action_type`, or autonomy, Phase 10 (AI Safety) becomes mandatory.>

## 12. Acceptance Criteria _(gate: dry-run validation)_

<!-- Phrase each EARS-style and observable/runnable: "WHEN <condition>, THEN <observable result>"
     (the testable form of the §5 "the system SHALL …"). These become the dry-run evidence in
     /deliver's FINAL-REPORT. Map every AC back to the FR(s) it covers. -->

| ID    | Acceptance criterion (WHEN … THEN …) | Covers FR(s) |
| ----- | ------------------------------------ | ------------ |
| AC-01 |                                      |              |

> **Requirement coverage footer (gate).** _N_ FRs total · _M_ mapped to ≥ 1 AC · **_K_ unmapped ⚠️**.
> Every FR in §5 MUST map to at least one AC above; any unmapped FR (`K > 0`) **blocks Definition of
> Ready / Done** until covered or explicitly moved to §3 Non-Goals. Fill the counts before review.

> The table above is the **canonical, machine-traceable** AC form. A Gherkin
> (Feature / Given-When-Then) companion is an **optional** human-readable form — see
> `docs/product/acceptance-criteria-standard.md`; each `Scenario` tags an `AC-NN`, the table stays
> authoritative.

## 13. Risks & Limitations

- <Known trade-offs; document, don't hide. Each significant one → an ADR consequence.>

## 14. ADR & Dependency Impact

- **Reuses:** <ADRs already governing this area.>
- **Adds:** <the ADRs in `new_adrs_required`.>
- **Produces:** dependency-manifest.yaml, pinned lockfiles, SBOM, OpenAPI/AsyncAPI spec, README, runbook stub, slo.yaml entries.

## 15. Open Questions

<!-- Anything that must be resolved at a HITL gate rather than assumed. /deliver lists these as open-HITL items. -->

1.

## 16. References

- <Specs, ADRs, papers, prior art.>
