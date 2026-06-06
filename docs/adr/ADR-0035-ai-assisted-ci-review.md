# ADR-0035: AI-Assisted CI Code Review

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Spec:** `.github/workflows/ci-ai-review.yml`
**Issue:** #8
**Related ADRs:** ADR-0029 (DevSecOps Pipeline Security), ADR-0034 (Agentic Escalation Protocol)

---

## Context

The CI pipeline enforces SAST (Bandit, SpotBugs, gosec), secret scanning, and PII
checks — all static, rule-based tools. They do not catch:

- Architectural drift (e.g., direct DB access from API layer)
- Missing spec references in the PR description
- Guardrail weakening that is syntactically valid
- Test coverage gaps relative to the scope of the change

These require contextual reasoning that static tools cannot provide. Gap 4.2 from the
_2026 Agentic Coding Trends Report_ identifies "agentic quality control" — AI reviewing
AI-generated code — as a mandatory trend for high-velocity agentic teams.

---

## Decision

Add `.github/workflows/ci-ai-review.yml`:

- **Trigger:** `pull_request` on `src/**`, `tests/**`, `specs/**` targeting `main` or `develop`.
- **Diff capture:** `gh pr diff` piped through `head -200` — caps token consumption
  and avoids overloading the model with large diffs.
- **Review prompt:** checks five dimensions against CLAUDE.md §3 and the SDD invariants:
  1. Spec reference presence in PR title/body
  2. Guardrail preservation (`src/guardrails/`, `src/agents/hitl_gateway.py`)
  3. Test coverage proportionality
  4. PII literal detection
  5. Architecture rule violations (direct DB access, `eval`, SQL concatenation, hardcoded secrets)
- **Model:** `claude-sonnet-4-6` — matches the active session model for consistency.
- **Output:** findings posted as a PR comment via `gh pr comment`.
- **Gate behaviour:** **informational only** — does not block merge. This is intentional;
  blocking requires operator confidence in the prompt quality over several sprints.
- **Skip mechanism:** label `skip-ai-review` suppresses the comment.
- **Graceful degradation:** if `ANTHROPIC_API_KEY` is absent (forks, template users),
  the job exits cleanly with a warning rather than failing.

---

## Consequences

**Positive:**

- Every PR touching `src/`, `tests/`, or `specs/` receives a structured architectural
  review that complements SAST — zero marginal developer effort.
- Catches spec-reference omissions before the `pr-governance` blocking gate fires,
  giving developers an earlier signal.
- Establishes the review prompt as a versioned artifact — improvements are tracked in git.

**Neutral:**

- Cost: ~1,000–2,000 tokens per review at $3/$15 per M → ~$0.015–$0.03 per PR.
  For 50 PRs/month: < $1.50/month. Covered by the LLM budget (ADR-0020).
- The 200-line diff cap means large refactors are reviewed only partially. Acceptable
  for the informational gate; revisit if promoting to blocking.

**Risk:**

- False positives in the AI review may create noise if the prompt is too aggressive.
  Mitigated by the informational-only posture; developers learn to calibrate.
- The `ANTHROPIC_API_KEY` secret must be added to the repository secrets by the operator.
  If absent, the job silently skips — no security regression, but no review either.

## Path to Blocking Gate

When the team has confidence in prompt quality (target: < 5% false-positive rate over
20 PRs), promote the gate by:

1. Parsing the "Overall: REVIEW_RECOMMENDED" line in the comment
2. Setting `exit 1` in the workflow when that verdict is returned
3. Updating this ADR status to "Amended" with the blocking date
