# ADR-NNNN — {Title in Title Case}

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-NNNN
**Date:** YYYY-MM-DD
**Authors:** {Name(s)}
**Spec:** {specs/... path, or "N/A — operational policy"}
**Supersedes:** {ADR-NNNN or None} | **Superseded by:** {ADR-NNNN or None}
**Milestone:** {vX.Y.Z — short description} _(optional)_
**Relates to:** {[ADR-NNNN](...), …} _(optional)_

> Copy this file to `docs/adr/ADR-NNNN-<kebab-title>.md`, fill every field, then add a row to the
> master index in `docs/adr/README.md` (a dead index link fails the CI governance gate). ADRs are
> **append-only and immutable** (AGENTS.md §5–§6, ADR-0059): never delete, move, or rewrite an
> accepted ADR — supersede it with a new one and mark the old one `Superseded by ADR-NNNN` in place.

---

## Context

What situation or problem prompted this decision? What constraints apply (technical, regulatory,
organisational, cost, time)? State the forces at play factually and ground every claim per
CLAUDE.md §3.6 — link the spec, code, or data that motivates the decision. Avoid proposing the
solution here.

## Decision

State what was decided, clearly and unambiguously, in active voice ("We will…"). One ADR records
**one** decision. If you find yourself deciding two unrelated things, split into two ADRs.

## Consequences

### Positive

What does this decision enable or improve?

### Negative / Trade-offs

What does it cost, constrain, or make harder? Be honest — an ADR with no trade-offs is usually
under-analysed.

### Neutral _(optional)_

Effects that are neither clearly good nor bad but worth recording.

## Alternatives Considered

What other options were evaluated, and why were they rejected? Include "do nothing" where relevant.
This section is what makes an ADR defensible months later.

## Compliance & Risk _(include when the decision touches security, privacy, or AI autonomy)_

- **Controls affected:** {OWASP/ASVS/GenAI control IDs, or "none"} — see `specs/security/*-control-matrix.yaml`
- **Data classification impact:** {L1–L4 surface changes, or "none"} — see `docs/data/data-classification.md`
- **Autonomy impact:** {does this change HITL/HOTL behaviour or a feature flag? ADR-0015}
- **Review/expiry:** {date this decision should be revisited, if temporary, else "permanent"}

---

## Related

- `docs/adr/README.md` — master index & lifecycle definition
- `docs/adr/adr-review-checklist.md` — checklist to apply before marking this ADR `Accepted`
