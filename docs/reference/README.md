# Reference

> **Owner:** Tech Lead | **Status:** Living reference
> Implementation-level references for people reading or extending the code — the "how it actually
> works", with file:line pointers. Distinct from `specs/` (what to build) and `skills/` (how to do a
> task): this is the annotated tour of the running system.

## Contents

| Doc                                            | Purpose                                                               |
| ---------------------------------------------- | --------------------------------------------------------------------- |
| [`request-lifecycle.md`](request-lifecycle.md) | End-to-end walkthrough: submit → consume → orchestrate → HITL → audit |

## How this relates to other docs

- `specs/system/request-pipeline.md` — the architectural **contract** (what the pipeline guarantees).
- `docs/sre/cuj/CUJ-001-user-request-processing.md`, `CUJ-002-hitl-decision-flow.md` — the **journeys**
  with SLOs.
- This directory — the **annotated implementation** mapping those to actual code.

## Related

- `docs/data/data-model-catalog.md` · `docs/data/erd.md` — the data the pipeline touches
- `docs/quickstart/` — getting the app running · `SETUP.md`
