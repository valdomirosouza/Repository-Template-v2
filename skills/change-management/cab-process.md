# Skill — CAB Process (Change Advisory Board)

**Owner:** Tech Lead | **Reviewer:** DevOps Lead | **Status:** Active | **Last updated:** 2026-05-28

Activate this skill when a change requires CAB review before deployment. Normal changes
(non-trivial, non-emergency) require CAB approval per the RFC process.

**Related:** `skills/change-management/rfc-process.md`, `skills/change-management/deploy-rollback.md`,
`docs/change-management/CAB-PROCESS.md`, `specs/sdlc/development-lifecycle.md §5`

---

## Change Types and CAB Requirement

| Change type   | Definition                                                                           | CAB required         | RFC required         |
| ------------- | ------------------------------------------------------------------------------------ | -------------------- | -------------------- |
| **Standard**  | Pre-approved, low-risk, well-understood (e.g. dependency patch, config tweak)        | No                   | No                   |
| **Normal**    | Non-trivial change with moderate risk (new feature, schema change, new external dep) | Yes                  | Yes — before CAB     |
| **Emergency** | P0/P1 hotfix deployed immediately; retrospective RFC within 24h                      | No (post-hoc review) | Within 24h of deploy |

---

## Normal Change Workflow

```
RFC drafted → RFC reviewed → CAB scheduled → CAB approves → Deploy window → Post-deploy review
```

### 1. Draft the RFC

Use the template: `docs/change-management/RFC-TEMPLATE.md`

Mandatory RFC sections:

- **Summary**: what is changing and why?
- **Risk assessment**: what can go wrong? How likely? How severe?
- **Rollback plan**: exact steps to undo if something goes wrong
- **Test plan**: how will you verify success in staging and production?
- **Affected systems**: which services, databases, queues, or external dependencies?
- **Deploy window**: proposed date/time and duration

Submit the RFC as a PR to `docs/change-management/rfc/`. Tag it `rfc` and assign reviewers.

### 2. RFC Technical Review (pre-CAB)

RFC reviewers (Tech Lead + affected service owners) must approve within **2 business days**.
If the change touches:

- `src/guardrails/` or `src/agents/hitl_gateway.py` → Security Lead approval required
- `infrastructure/feature-flags/` → AI Governance Lead approval required
- `docs/privacy/` or any PII processing → DPO approval required
- `.github/workflows/` → DevOps Lead approval required

### 3. CAB Meeting

CAB meets weekly (or on-demand for time-sensitive Normal changes).

**CAB composition:**

- Tech Lead (chair)
- SRE Lead
- Security Lead (for security-impacting changes)
- DevOps Lead
- Affected service owner

**CAB review checklist:**

- [ ] RFC is complete and approved by technical reviewers
- [ ] Rollback plan is tested in staging or documented as tested previously
- [ ] Deploy window is in a low-traffic period (prefer weekday 10:00–14:00 local time)
- [ ] On-call engineer is aware and available during the deploy window
- [ ] Monitoring dashboard is open and alert routing confirmed
- [ ] For DB schema changes: migration has been tested on a staging DB snapshot

**Decision:** Approve / Approve with conditions / Defer / Reject.
Record the outcome in the RFC PR as a review comment.

### 4. Deploy Window

Deploy only within the approved window. If the deploy cannot complete within the window:

- Stop, roll back if partially deployed
- Re-schedule via CAB

### 5. Post-Deploy Review

Within 24 hours of the deploy:

- Confirm Golden Signals are normal
- Mark the RFC PR as `merged` with a comment: "Deployed successfully at {timestamp}"
- If issues were found: document in the RFC and open a follow-up ticket

---

## Emergency Change (Hotfix)

Emergency changes bypass CAB but are not ungoverned:

1. Deploy immediately following the hotfix path in `specs/sdlc/development-lifecycle.md §7`
2. Notify the CAB chair (Tech Lead) within 1 hour of deploy
3. File a retrospective RFC in `docs/change-management/rfc/` within 24 hours
4. CAB reviews the retrospective RFC at the next meeting

---

## CAB Escalation

If a change requires CAB approval but is blocking a release:

- Contact the CAB chair directly for an emergency CAB session (can be async via Slack/email)
- Minimum quorum: CAB chair + one other CAB member
- Document the emergency session outcome in the RFC PR

Never deploy a Normal change without CAB approval. Violations must be reported to
the CAB chair and documented as an incident in `docs/postmortems/`.
