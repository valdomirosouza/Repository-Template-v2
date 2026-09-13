# Retrospective — FEAT-001 HTTP Golden Signals (SPEC-FEAT-001)

> **Phase:** 14 (Post-Deployment & Learn) · **Issue:** #357 · **Date:** 2026-09-12 · **Facilitator:** Tech Lead
> Scope: the delivery cycle through Phase 11 (release phases pending, see `docs/delivery/SPEC-FEAT-001/FINAL-REPORT.md`).

## What went well

- The wiring invariant (ADR-0089) caught the class of defect this feature fixes: a metric defined and never populated. The lifespan test now guards it.
- The feature was small enough that every template section is real — a usable worked example for `specs/features/`.

## What did not

- The feature shipped in Wave 12 (#365) before its spec existed; the spec was back-filled in Wave 13. That is the exact "code before spec" pattern the template forbids (CLAUDE.md §3.4) — recorded here rather than hidden.
- Two of the three products of Phase 2 (discovery, NFR) were written after the code, so their "options considered" is a reconstruction.

## Actions

| Action                                                                                  | Owner     | Tracked in |
| --------------------------------------------------------------------------------------- | --------- | ---------- |
| The PR spec-reference gate now verifies a binding spec exists before code (W13-T5)      | Tech Lead | #370       |
| Phase 12–14 evidence appended when PR #365 is released                                  | Release   | #357       |
