# ADR Alignment Review — Agentic Spec-Driven Delivery Workflow

> **Type:** Assessment record (read-only review). **Date:** 2026-06-07
> **Scope:** all 59 ADRs (`docs/adr/ADR-0001` … `ADR-0059`) at the `main` tip after v2.10.1.

## Objective

Validate whether each ADR stays up to date with the **Agentic Spec-Driven Delivery
Workflow** (ADR-0052 → ADR-0058; canonical doc `docs/sdlc/agentic-spec-driven-delivery.md`),
and classify each as **Aligned**, **Still-critical (not workflow-specific)**, or
**Stale/Deprecated → move to `deprecated/`**.

## Verdict

**No ADR is stale or deprecated.** All 59 are in force. **Nothing was moved to
`deprecated/`.** One clarifying cross-reference note was added to ADR-0054 (see below).

| Bucket                                                     | Count |
| ---------------------------------------------------------- | ----- |
| Aligned with the workflow (serve a phase/gate)             | ~40   |
| Still-critical (foundational, orthogonal to the SDLC flow) | ~19   |
| Stale / Deprecated                                         | **0** |

## Method

Read every ADR; checked Status, supersession/cross-references, and whether any decision is
contradicted by a newer ADR or references an outdated phase model. Verified against the
repository, CI governance gate (ADR-index link validation), and `phase-gates.yaml`.

## Classification

### Aligned (decision current; directly serves a phase or gate)

0006 (canary → Phase 13), 0010, 0011, 0012, 0013, 0014, 0015, 0016, 0017, 0021,
0022 (testing → Phase 8), 0024, 0027 (CAB → Phase 12–13), 0028 (DORA → Phase 14),
0029 (DevSecOps → Phase 9), 0031, 0034, 0035, 0036, 0037, 0038 (learn → Phase 14),
0039, 0040, 0041, 0043, 0044, 0045, 0046, 0047, 0048, 0049, 0050, 0051, 0052, 0053,
0054, 0055, 0056, 0057, 0058, 0059.

### Still-critical (foundational; orthogonal to the SDLC flow, not changed by it)

0001, 0002, 0003, 0004, 0005, 0007, 0008, 0009, 0018, 0019, 0020, 0023, 0025, 0026, 0030, 0042.

### Stale / Deprecated

None.

## Key verifications

- **ADR-0052 (13-phase)** — Status `Accepted (extended by ADR-0058)` with a blockquote
  documenting the 13→15 evolution and "the decisions in this ADR remain in force." Aligned.
- **ADR-0058** — the current canonical 15-phase (0–14) definition.
- **ADR-0042–0046** — all `Status = Accepted` (table-format header; not blank).
- **ADR-0054** — its two "13 phases" mentions are historically accurate (Context as-authored +
  a correct citation of ADR-0052). A clarifying "extended by ADR-0058" cross-ref note was
  added to its header (the `phase-gates.yaml` machinery is already on the 15-phase model).
- **ADR-0002** — baseline-version update is already noted (ADR-0059). Aligned.

## Why no ADR was moved (governance)

ADRs are **append-only and immutable** in this repository (AGENTS.md §5–§6, ADR-0059):
_"do not remove or alter existing ADRs — mark superseded ones as `Superseded`."_ Moving an
ADR file would additionally **break the CI governance gate** (which validates every
`docs/adr/README.md` index link points to an existing file) and break cross-references from
other ADRs, specs, and code. The correct treatment for a future deprecated ADR is therefore
to **mark it `Superseded by ADR-NNNN` in place**, never to relocate it.

## Outcome

- Added a phase-model cross-ref note to `docs/adr/ADR-0054-machine-readable-governance-contracts.md`.
- No files moved or deleted. The ADR set is internally consistent and current.
