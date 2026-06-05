# Dual-Use Risk Assessment Registry

**Owner:** AI Governance Lead
**Updated:** 2026-06-05
**Process:** `specs/ethics/ethical-ai-principles.md §4`

Every new `action_type` registered in the agent registry must have an entry here before
activation. Entries are append-only — supersede rather than delete when re-assessed.

---

## Registry Format

```yaml
- action_type: <name>
  assessed_by: <name, role>
  assessment_date: <YYYY-MM-DD>
  dual_use_risks:
    - question: D-01 # enumerate/probe/attack external systems
      answer: yes | no
      mitigation: <description if yes>
      adr_reference: ADR-XXXX # if mitigation is governed by an ADR
    - question: D-02 # generate/execute/transmit code without human review
      answer: yes | no
      mitigation: <description if yes>
      adr_reference: ADR-XXXX
    - question: D-03 # access credentials/keys/tokens
      answer: yes | no
      mitigation: <description if yes>
      adr_reference: ADR-XXXX
    - question: D-04 # scrape/exfiltrate/aggregate PII at scale
      answer: yes | no
      mitigation: <description if yes>
      adr_reference: ADR-XXXX
    - question: D-05 # outbound HTTP to user-controlled URLs
      answer: yes | no
      mitigation: <description if yes>
      adr_reference: ADR-XXXX
    - question: D-06 # harm to third parties if misused
      answer: yes | no
      mitigation: <description if yes>
      adr_reference: ADR-XXXX
  approved: true | false
  approval_notes: <optional rationale or conditions>
```

---

## Registered Action Types

_No action types registered yet. Add an entry for each `action_type` before activation._
