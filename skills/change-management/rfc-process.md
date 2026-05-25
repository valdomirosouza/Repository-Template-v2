# Skill — RFC Process

**Owner:** Tech Lead | **Reviewer:** DevOps Lead | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill for any Normal or Emergency change request.

---

## When to File an RFC

| Change type | Trigger                                                               | RFC required?                 |
| ----------- | --------------------------------------------------------------------- | ----------------------------- |
| Standard    | Bug fix, minor enhancement, docs update                               | No                            |
| Normal      | New feature, dependency upgrade, infra change, guardrail modification | Yes — before implementation   |
| Emergency   | P1 hotfix in production                                               | Yes — within 24 h after merge |

When in doubt: file the RFC. It protects you and the team.

---

## How to Complete the RFC Template

File: `docs/change-management/RFC-TEMPLATE.md`

1. Copy the template to `docs/change-management/rfc/RFC-<NNN>-<short-title>.md`
2. Assign the next sequential RFC number
3. Complete all required sections:

| Section             | What to include                                            |
| ------------------- | ---------------------------------------------------------- |
| Summary             | One paragraph; what changes and why                        |
| Motivation          | Problem being solved; why now                              |
| Design              | Technical approach; alternatives considered                |
| Privacy impact      | New PII fields? New processing purpose? DPIA/RIPD needed?  |
| Security impact     | New attack surface? Permission changes? Guardrail changes? |
| Rollout plan        | Deploy strategy, monitoring window, rollback plan          |
| Acceptance criteria | Measurable conditions that define success                  |
| Approval table      | Sign-off rows for each required approver                   |

4. Open a GitHub issue using the Change Request template and link the RFC document

---

## CAB Submission Requirements

For Normal changes, submit to CAB (Change Advisory Board) at least **3 business days** before the planned deploy date.

Required in the submission:

- Completed RFC document
- GitHub issue number
- Linked spec (`specs/*`)
- Linked PR (if already open)
- Deploy date and maintenance window (if needed)
- Rollback plan with estimated rollback time

Submit by creating or updating the GitHub issue with the `cab-review` label.

---

## Getting Approvals

Required approvers depend on what the change touches:

| Change scope                      | Required approvers     |
| --------------------------------- | ---------------------- |
| Any change                        | Tech Lead              |
| Infrastructure or deploy pipeline | SRE Lead + DevOps Lead |
| Guardrails or security controls   | Security Lead          |
| PII processing or privacy policy  | DPO                    |
| Agent behaviour or HITL logic     | AI Governance Lead     |
| CAB formal approval (Normal)      | CAB majority vote      |

Approvals are recorded in the RFC document's approval table with date and signature.

---

## Emergency Change Process

For P1 incidents requiring immediate production fix:

1. Implement fix on a hotfix branch
2. Get minimum two approvers: Tech Lead + SRE Lead (or Security Lead if security-related)
3. Merge and deploy
4. **Within 24 hours**: file the RFC document retrospectively
5. **Within 48 hours**: notify CAB of the emergency change
6. Schedule post-mortem within 5 business days

Document the emergency designation in the PR description:

```
Change Type: Emergency
RFC: docs/change-management/rfc/RFC-<NNN>-<title>.md (filed retrospectively)
```

---

## How to Reference the RFC

In the PR description:

```
RFC: docs/change-management/rfc/RFC-<NNN>-<title>.md
```

In the commit message:

```
feat(scope): description

Refs: #<issue>, RFC-<NNN>, SPEC-<domain>
```

In `CHANGELOG.md` under `[Unreleased]`:

```markdown
### Changed

- Description of change (RFC-NNN, #issue)
```
