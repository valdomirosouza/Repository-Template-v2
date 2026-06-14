# ADR Review Checklist

> **Owner:** Tech Lead | **Applies to:** every ADR before it moves `Proposed → Accepted`
> Use alongside `docs/adr/ADR-TEMPLATE.md`. The master index and lifecycle definition live in
> `docs/adr/README.md`.

The ADR lifecycle is **Proposed → Accepted → Deprecated → Superseded** (`docs/adr/README.md`).
ADRs are **append-only and immutable** (ADR-0059): a decision is changed by writing a _new_ ADR and
marking the old one `Superseded by ADR-NNNN` in place — never by editing or deleting the file.

## Before marking an ADR `Accepted`

### Structure & metadata

- [ ] Filename is `docs/adr/ADR-NNNN-<kebab-title>.md` and `NNNN` is the next free number
- [ ] Header has **Status**, **Date**, **Authors**; `Supersedes` / `Superseded by` set (or `None`)
- [ ] Added to the master index table in `docs/adr/README.md` (CI fails on a dead index link)
- [ ] Exactly **one** decision recorded (two decisions ⇒ split into two ADRs)

### Content quality

- [ ] **Context** states the real forces/constraints, with every factual claim grounded (CLAUDE.md §3.6)
- [ ] **Decision** is unambiguous and in active voice
- [ ] **Consequences** include genuine **Negative / Trade-offs**, not only positives
- [ ] **Alternatives Considered** lists real options (incl. "do nothing") and why each was rejected
- [ ] No fabricated APIs, flags, file paths, or ADR numbers — links resolve

### Cross-references (traceability)

- [ ] Linked to its **spec** (`specs/...`) and, if it governs a service, reflected in `services.yaml` `adr:`
- [ ] If it supersedes an ADR, that ADR's status is updated to `Superseded by ADR-NNNN` **in the same PR**
- [ ] `Relates to` lists adjacent ADRs so the decision graph stays navigable

### Compliance & risk (when applicable)

- [ ] Security/privacy/AI-autonomy impact assessed in the **Compliance & Risk** section
- [ ] Control-matrix impact noted (`specs/security/asvs-control-matrix.yaml`, `owasp-genai-control-matrix.yaml`)
- [ ] Data-classification impact noted (`docs/data/data-classification.md`) if data surface changes
- [ ] Autonomy/feature-flag changes carry governance sign-off (ADR-0015); else "no autonomy impact"
- [ ] An **expiry/review date** is set for any explicitly temporary decision

### Governance gate

- [ ] Touching > 3 ADRs at once? → that is an escalation trigger (CLAUDE.md §14.1) — stop and escalate
- [ ] Author is not the sole approver where dual-approval paths apply (CODEOWNERS, SOX §10)

## When deprecating or superseding

- [ ] Old ADR's status line updated **in place** to `Deprecated (YYYY-MM-DD)` or `Superseded by ADR-NNNN`
- [ ] The superseding ADR's `Supersedes:` field names the old ADR
- [ ] No ADR file is deleted, moved, or renamed (breaks index + cross-references + CI gate)

---

## Related

- `docs/adr/ADR-TEMPLATE.md`
- `docs/adr/README.md` — lifecycle & master index
- `docs/repository-maintenance/adr-alignment-review.md` — periodic alignment assessment
