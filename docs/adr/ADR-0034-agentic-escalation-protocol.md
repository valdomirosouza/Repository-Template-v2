# ADR-0034: Agentic Escalation Protocol

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Spec:** CLAUDE.md §14
**Issue:** #3
**Related ADRs:** ADR-0011 (HITL/HOTL), ADR-0015 (Feature Flags), ADR-0016 (Sandbox)

---

## Context

As Claude Code sessions grow in autonomy and task horizon, the risk of an agent taking
an unreviewed high-impact action increases. The HITL gateway (`src/agents/hitl_gateway.py`)
handles runtime action routing, but no behavioral contract existed to tell Claude Code
_when to stop and ask_ during a session — before touching files, not after.

Without explicit escalation triggers, agents can:

- Modify multiple ADRs simultaneously, creating architectural drift without human review
- Touch guardrail code with only one approver instead of the required dual-approval path
- Proceed without a spec reference, violating the SDD invariant
- Reduce test coverage below acceptable thresholds
- Change feature flags that control HITL/HOTL autonomy levels

These failure modes were identified during analysis of the _2026 Agentic Coding Trends
Report_ gap assessment (Gap 4.1: no "when to ask for help" behavioral rule).

---

## Decision

Add a mandatory **Agentic Escalation Protocol** to `CLAUDE.md §14` that defines:

1. **Six hard escalation triggers** — conditions under which Claude Code MUST emit a
   `[HITL-ESCALATE]` block and stop all file writes until a human explicitly resolves it.

2. **A structured escalation block format** — `reason`, `proposed_action`, `risk_level`,
   `files_affected`, `awaiting_human_decision` — so humans can make an informed decision
   quickly and the event is machine-parseable for audit.

3. **A non-escalation acknowledgement format** — `[HITL-NOTE]` — for near-miss situations
   where the agent continues but documents its reasoning for human review.

The six triggers are:

| Trigger                                                 | Rationale                                        |
| ------------------------------------------------------- | ------------------------------------------------ |
| > 3 ADRs modified simultaneously                        | Architectural scope requires human judgment      |
| Touch `src/guardrails/` or `src/agents/hitl_gateway.py` | Dual-approval paths required                     |
| Spec not found after two searches                       | SDD invariant: no code without a spec            |
| Test coverage would drop below 75%                      | Quality gate                                     |
| Feature flag enable/disable/modify                      | Autonomy level changes require ADR-0015 sign-off |
| Escalation already emitted and unresolved in session    | Cascading escalations cannot self-resolve        |

---

## Consequences

**Positive:**

- Agents proactively surface high-risk situations before irreversible actions are taken.
- The structured block format makes escalations auditable and machine-parseable.
- Aligns CLAUDE.md behavioral contract with the HITL gateway runtime contract.
- Reduces the blast radius of autonomous agent errors in sensitive code paths.

**Neutral:**

- Agents will pause more frequently on complex cross-cutting tasks — by design.
- Teams with full autonomy approval (ADR-0015 FULL mode) may find some triggers
  conservative; they can document exceptions in ADR-0015 rather than weakening this ADR.

**Risk:**

- Over-triggering on legitimate tasks could reduce agent throughput. Mitigated by the
  `[HITL-NOTE]` path for near-miss situations that do not actually meet a trigger.
- This protocol governs Claude Code sessions only, not the runtime HITL gateway.
  It is a complementary, not a replacement, control.
