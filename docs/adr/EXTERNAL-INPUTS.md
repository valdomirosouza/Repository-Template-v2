# ADR External Input Documents — Reference Resolution

Several ADRs cite **driver/input documents** by bare filename in their `Refs:`/`References`
sections (e.g. "§Pillar 1", "§2"). Those documents were the external assessments and directives
that motivated the decisions; they have since been **archived under `/deprecated/`** at the repo
root. They are intentionally retained (not deleted) so the grounding chain for those ADRs stays
resolvable, but they are **historical inputs, not living specs** — do not treat their section
numbers as current contracts.

The 2026-06-16 ADR audit flagged these as "phantom" because they do not resolve at the bare path
cited; this note records where they actually live.

| Cited driver document                              | Resolves to                                                                                                                         | Cited by                                         |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `secure-by-design-agentic-ai-compliance-v2.md`     | [`/deprecated/secure-by-design-agentic-ai-compliance-v2.md`](../../deprecated/secure-by-design-agentic-ai-compliance-v2.md)         | ADR-0047, ADR-0048, ADR-0049, ADR-0050, ADR-0051 |
| `Agentic-SDLC-Repository-Improvement-Directive.md` | [`/deprecated/Agentic-SDLC-Repository-Improvement-Directive.md`](../../deprecated/Agentic-SDLC-Repository-Improvement-Directive.md) | ADR-0053, ADR-0054, ADR-0055, ADR-0056, ADR-0057 |
| `agentic-sdlc-e2e-workflow-v2.md`                  | [`/deprecated/agentic-sdlc-e2e-workflow-v2.md`](../../deprecated/agentic-sdlc-e2e-workflow-v2.md)                                   | ADR-0052                                         |

## Guidance for future ADRs

- When an ADR is driven by an external assessment, **either** commit that input under `/deprecated/`
  (as here) **and** cite it with a repo-relative path, **or** anchor the decision to an in-repo
  `specs/` document. Do not cite a bare filename that lives outside the ADR's own directory.
- The planned **ADR/RFC reference-validator gate** (audit follow-up) should treat a citation that
  resolves under `/deprecated/` as a _warning_ (historical input) rather than a hard failure, but
  flag a citation that resolves _nowhere_ as an error.
