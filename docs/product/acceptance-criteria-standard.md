# Acceptance Criteria Standard — Gherkin + WHEN/THEN

> **Owner:** Product Owner + Tech Lead | **Phase:** 4 (Specification) · 8 (Testing)
> **Status:** Approved | **Refs:** issue #275
> **Governance:** `docs/process/HITL-GOVERNANCE.md`

This standard defines how acceptance criteria (AC) are written in this repository. It introduces
the **Gherkin** (Feature / Scenario / Given–When–Then) behavioural form and pins how it coexists
with the **WHEN/THEN table** that `specs/SPEC-TEMPLATE.md` §12 already mandates.

---

## Two forms, one source of truth

The repository keeps **two complementary representations** of acceptance criteria:

| Form                            | Lives in                                                          | Optimised for                                                  | Role                                                                                                        |
| ------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **WHEN/THEN table** (canonical) | `SPEC-TEMPLATE.md` §12 — `AC-NN \| WHEN … THEN … \| Covers FR(s)` | Machine traceability, gate evidence, FR→AC coverage footer     | **Authoritative.** Each `AC-NN` is the stable id used by the coverage gate and the `/deliver` FINAL-REPORT. |
| **Gherkin** (companion)         | Spec §12 (optional fenced block) or a `.feature` file             | Human readability, BDD test scaffolding, edge-case enumeration | **Derived.** Each `Scenario` rephrases one `AC-NN` behaviourally; it never replaces the table.              |

Rules:

1. The **WHEN/THEN table stays the machine-traceable form.** Ids (`AC-01`, …), the
   `Covers FR(s)` column, and the **coverage footer** gate live there and are not duplicated in
   Gherkin.
2. **Gherkin is the human-readable behavioural form.** It is _optional_ and _additive_. When
   present, every `Scenario` must tag the `AC-NN` it elaborates so the two forms stay in lockstep.
3. If the two ever disagree, **the table wins** (it is what gates read). Fix the Gherkin.

---

## Gherkin grammar (house rules)

```gherkin
Feature: <feature name — matches the spec title>

  Scenario: <one observable behaviour>   # @AC-NN — the table row this elaborates
    Given <precondition / system state>
    When  <single trigger or action>
    Then  <observable, checkable result>
    And   <additional observable result>   # optional
```

- One `Scenario` per `AC-NN`. Keep `When` to a **single** trigger (split compound triggers into
  separate scenarios — this mirrors the EARS "WHEN … SHALL …" style used in §5/§12).
- `Then` must be **observable and runnable** (a status code, a stored value, a metric), never an
  internal/implementation detail.
- Tag the originating `AC-NN` in a trailing comment (or a `@AC-NN` tag in a `.feature` file) so
  traceability is preserved.

---

## Worked examples (grounded in SPEC-LGS-001)

The following rephrase real acceptance criteria from
`specs/system/SPEC-LGS-001-log-based-golden-signals.md` §12. The table rows are the canonical
form; the Gherkin blocks are the companion behavioural form.

### Canonical (excerpt of the §12 table)

| ID    | Acceptance criterion (WHEN … THEN …)                                                                      | Covers FR(s) |
| ----- | --------------------------------------------------------------------------------------------------------- | ------------ |
| AC-02 | WHEN a malformed batch is posted THEN it is rejected `422`; a valid batch returns `202` with counts.      | FR-01        |
| AC-08 | WHEN high-latency data is seeded THEN `recommended_action_mode` flips to `HITL` and approval is required. | FR-13        |

### Companion (Gherkin)

```gherkin
Feature: Log-based Golden Signals ingestion & governance

  Scenario: Malformed ingestion batch is rejected   # @AC-02 — covers FR-01
    Given the ingestion API is running and authenticated
    When  a batch that is not a valid JSON array is posted to POST /ingestion
    Then  the response status is 422
    And   nothing from the batch is persisted

  Scenario: Valid ingestion batch is accepted        # @AC-02 — covers FR-01
    Given the ingestion API is running and authenticated
    When  a well-formed batch is posted to POST /ingestion
    Then  the response status is 202
    And   the body reports accepted and rejected counts

  Scenario: Threshold breach flips governance to HITL  # @AC-08 — covers FR-13
    Given the analytics pipeline has aggregated recent windows
    When  high-latency entries push P99 over HITL_P99_LATENCY_MS
    Then  the analytics _governance block sets recommended_action_mode to "HITL"
    And   human_approval_required is true
```

---

## FR → AC traceability requirement

Traceability is enforced on the **canonical table**, not on Gherkin:

- **Every FR in §5 MUST map to at least one `AC-NN`** via the `Covers FR(s)` column. Any unmapped
  FR (`K > 0` in the §12 coverage footer) **blocks Definition of Ready / Done** until covered or
  explicitly moved to §3 Non-Goals.
- When a Gherkin companion is provided, **every `Scenario` MUST tag an existing `AC-NN`** — a
  scenario with no table row, or an `AC-NN` with no FR, is a traceability defect.
- The chain is therefore: **FR (§5) → AC-NN (§12 table) → Scenario (Gherkin, optional) → test**
  (see the spec's traceability matrix, e.g. SPEC-LGS-001 §6).

## Related

- `specs/SPEC-TEMPLATE.md` — §5 FR, §12 Acceptance Criteria (binding template)
- `docs/product/nfr-taxonomy.md` — NFR taxonomy (companion)
- `skills/sdlc/spec-lifecycle.md` · `skills/engineering/testing-strategy.md`
- `specs/system/SPEC-LGS-001-log-based-golden-signals.md` — source of the worked examples
