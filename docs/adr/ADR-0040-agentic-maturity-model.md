# ADR-0040: Agentic Maturity Self-Assessment Model

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Issue:** #17
**Related ADRs:** ADR-0034 (Escalation Protocol), ADR-0037 (Governance Gate), ADR-0038 (Learn Stage), ADR-0039 (Tool Registry)

---

## Context

Gartner warns against "agent-washing" — labelling basic automation or prompt chains
as agents to inflate perceived AI maturity. When teams adopt this repository template
and declare "Augmentation-level" maturity without meeting the structural prerequisites,
governance gaps emerge that ultimately drive the 40% project cancellation rate.

Gap G1 from the Gartner Agentic AI Compliance gap analysis (2026-06-05): the repository
has no formal, machine-checkable definition of maturity level criteria.

---

## Decision

Introduce a maturity assessment script (`scripts/agentic_maturity_check.py`) that
evaluates the live repository file-system and flag configuration against four
machine-checkable criteria sets corresponding to the Gartner maturity levels:

| Level | Name         | Key criteria                                                          |
| ----- | ------------ | --------------------------------------------------------------------- |
| 1     | Assistance   | agents module + HITL gateway + CLAUDE.md                              |
| 2     | Automation   | tool registry ≥ 1 tool + audit logger + unit tests                    |
| 3     | Augmentation | full harness + FeedbackLearner + SubAgentRegistry + SessionCheckpoint |
| 4     | Autonomy     | learning-mode=active + context_graph.py + autonomy-tier-ready=true    |

The script is exposed via `make agentic-maturity-check` and integrated into `ci.yml`
as an informational, non-blocking `agentic-maturity` job that posts the report as a
PR comment on every pull request.

The check is intentionally file-system based (not runtime) so it runs in CI without
a live infrastructure stack.

---

## Consequences

**Positive:**

- Teams cannot falsely claim a higher maturity level than the repository actually supports
- The report tells them exactly which criteria are missing and how to close them
- PR-level annotation makes maturity regression visible before it reaches main

**Negative:**

- File-system checks are a proxy for runtime behaviour — a file can exist without
  being wired in correctly. Deeper validation (integration tests) is the complement.
- The `learning-mode=active` check inspects the flag default; a runtime override
  via flagd evaluation context would not be detected.

**Neutral:**

- The script has no external dependencies beyond the Python stdlib — runs in any
  CI environment without package installation.

---

## Alternatives Considered

- **Runtime evaluation only:** Check actual settings values via the running API.
  Rejected — requires a live stack in CI; too fragile for an informational gate.

- **Badge in README:** A static badge updated manually. Rejected — no enforcement,
  drifts immediately, exactly the "agent-washing" pattern we're preventing.
