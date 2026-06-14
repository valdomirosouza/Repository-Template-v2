# Product Discovery Artefacts

> **Owner:** Product Owner | **Phase:** 1–2 (Conception & Discovery)
> **ADR:** ADR-0052 | **Governance:** `docs/process/HITL-GOVERNANCE.md`

This directory contains agent-generated and human-approved discovery artefacts for each feature. Every document here is version-controlled and reviewed via PR — the repository itself is the system of record.

---

## Directory Structure

```
docs/product/
├── state-template.yaml  ← Template for per-feature state manifests (copy into FEAT-{id}/)
└── FEAT-{id}/
    ├── state.yaml       ← Machine-readable feature state (phase, approvals, gates, allowed actions)
    ├── discovery.md      ← Phase 1: Agent-generated Discovery Primer; reviewed by Product + Tech Lead
    ├── nfr.md            ← Phase 2: NFR doc; Security Lead approval mandatory
    ├── decisions.log     ← Chronological log of key decisions made during discovery
    └── spike-{slug}.md   ← Optional: spike findings (from a spike Issue)
```

`{id}` matches the GitHub Issue number for the parent feature request.

---

## Discovery Templates

Reusable templates live under `docs/product/templates/`. Copy the relevant ones into
`docs/product/FEAT-{id}/` for product-facing features (see the Definition of Ready). Go-to-market
templates for features intended as reusable products live under `docs/gtm/` (see
`docs/gtm/GTM-README.md`).

| Template                              | Purpose                                            |
| ------------------------------------- | -------------------------------------------------- |
| `templates/problem-framing-canvas.md` | Evidence the problem before specifying a solution  |
| `templates/personas.md`               | User persona vs buyer persona                      |
| `templates/user-story-map.md`         | Story map + AC → test → observability mapping      |
| `templates/value-hypothesis.md`       | Falsifiable value bet with kill criteria           |
| `templates/success-metrics.md`        | North-star, leading/lagging, and guardrail metrics |

---

## Agent-Disclosure Header

Every agent-generated document in this directory **must** include the following header block immediately after the title:

```markdown
> **⚡ Agent-Generated:** This document was drafted by Claude Code on {date}.
> **Human Review Required:** {role(s)} must review and approve before this artefact is actioned.
> **Review Status:** Draft | Under Review | Approved
> **Reviewer:** {name} | **Approved:** {date}
```

This satisfies EU AI Act transparency requirements (Article 13) and provides the accountability trail required by enterprise governance audits.

---

## Governance Rules

1. **Discovery artefacts do not pass through the runtime HITL gateway.** They follow Spec-as-PR governance: submit as a GitHub PR; human review is the HITL equivalent for pre-code phases. See `docs/process/HITL-GOVERNANCE.md`.

2. **The `nfr.md` is a security gate, not just a planning artefact.** It must be approved by the Security Lead before the related Issue can enter a sprint (DoR gate). This satisfies ISO 27001 A.8.25 and LGPD/GDPR Article 25 (data protection by design).

3. **The `decisions.log` is append-only.** Each entry records: decision, rationale, who made it, and date. Do not edit past entries.

4. **The `state.yaml` is the machine-readable source of feature state.** Copy `state-template.yaml` into `FEAT-{id}/state.yaml` when the feature package is created, and keep `current_phase`, `approvals`, and `gates_passed` current as the feature advances. Agents read `state.yaml` to determine the current phase and then consult `docs/process/gates/phase-gates.yaml` to learn which actions are allowed — without parsing any Markdown. The `next_allowed_agent_actions` / `prohibited_agent_actions` fields are a convenience projection of `phase-gates.yaml` for the current phase and MUST stay consistent with it (ADR-0054).

5. **Minimum reviewers per artefact:**

   | Artefact          | Minimum Reviewers                                       | Blocking Gate                       |
   | ----------------- | ------------------------------------------------------- | ----------------------------------- |
   | `discovery.md`    | Product Owner + Tech Lead                               | Viability confirmed                 |
   | `nfr.md`          | Security Lead (required) + Tech Lead                    | Security Lead approval is mandatory |
   | `feature-spec.md` | Tech Lead + Security Lead (if security surface changed) | CI governance + spec lint           |

---

## Creating a New Feature Discovery Package

When a new feature Issue is created:

```bash
# Manually, or via agent session bootstrap (Phase 1, Step 2):
FEAT_ID=<github-issue-number>
mkdir -p docs/product/FEAT-${FEAT_ID}
cp docs/product/state-template.yaml docs/product/FEAT-${FEAT_ID}/state.yaml
touch docs/product/FEAT-${FEAT_ID}/discovery.md
touch docs/product/FEAT-${FEAT_ID}/nfr.md
touch docs/product/FEAT-${FEAT_ID}/decisions.log
```

Then set `feature_id`, `title`, and `github_issue` in the new `state.yaml`.

Link `docs/product/FEAT-{id}/discovery.md` in the GitHub Issue body under "Discovery Link".

---

## decisions.log Format

```
# decisions.log — FEAT-{id}: {Feature Name}
# Append-only. Do not edit past entries.

---
[{date}] {Decision title}
Decision: {what was decided}
Rationale: {why}
Made by: {name / role}
---
```
