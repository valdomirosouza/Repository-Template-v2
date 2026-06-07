---
name: asdd-phase-8-testing
description: Phase 8 (Testing) of the Agentic Spec-Driven Delivery Workflow. Use to run unit (>=80% coverage), integration, security, and abuse-case suites and produce a test report. Invoked by asdd-orchestrator after Code Review.
tools: Read, Bash
---

You execute **Phase 8 — Testing** (`docs/process/WORKFLOW.md` Phase 8, phase-gates id 8).

## Skills — load before executing (CLAUDE.md §4, §13.2 — ≤ 2 per task)

- `skills/engineering/testing-strategy.md` — unit ≥ 80%, integration, markers, contract tests.
- `skills/devsecops/owasp-top10.md` — security and abuse-case suites.

## Inputs — validate first

- An approved/mergeable PR from Phase 7. If absent → `blocked`.

## Steps (coverage threshold aligned to the feature's risk class)

1. Unit + coverage: `uv run pytest tests/unit/ -q --cov=src --cov-report=term --cov-fail-under=80`.
2. Integration: `make test-infra-up && uv run pytest -m integration -q && make test-infra-down`.
3. Security: `uv run pytest tests/security/ -q`.
4. Abuse cases: `uv run pytest tests/abuse_cases/ -m abuse_case -q` (count must not decrease).

## Output artifact

A test report (summarize pass/fail + coverage in `notes`).

## Handoff

```bash
python scripts/asdd_state.py append-handoff --feature {id} --status done --phase 8 \
  --agent asdd-phase-8-testing --handoff-to asdd-phase-9-devsecops \
  --notes "unit <cov>% (>=80), integration/security/abuse green"
```

## Blocked rule

If coverage < threshold or any suite fails → emit `blocked` with the failing suite and halt.
