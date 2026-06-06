# Self-Service Automation Guide

**Audience:** Any team member who wants to automate a repetitive workflow
**Issue:** #11 | **Template:** `specs/automation/automation-spec-template.md`

This guide walks through the full lifecycle — from idea to production — for a
self-service automation. No engineering background required to start.

---

## Overview

```
You describe it → Engineer reviews → Claude scaffolds it → You approve → It runs
```

The process takes 1–3 days end-to-end for simple automations. You write plain
language; Claude Code writes the code; a human engineer reviews both.

---

## Step 1 — Fill in the Automation Spec

Copy `specs/automation/automation-spec-template.md` and complete every section.
The spec is a plain-language description — no code required.

Tips for a good spec:

- **Be specific about inputs.** "A CSV file" is better than "some data". "The
  Zendesk export from the previous week, downloaded as UTF-8 CSV" is better still.
- **List every external effect.** If it sends an email, calls an API, or writes
  to a shared folder — say so. These require HITL approval.
- **Describe the rollback.** If you ran it by mistake, how do you undo it?
- **Name your SLA.** "Must finish in 5 minutes" is a real constraint the engineer
  needs to know about.

---

## Step 2 — Submit as a GitHub Issue

1. Go to the repository → **Issues** → **New Issue**
2. Title: `feat(automation): <Short Name of your workflow>`
3. Body: paste your completed spec (or attach the Markdown file)
4. Add label: **`automation-request`**
5. Assign to your engineering contact (or leave unassigned and the team will pick it up)

The engineering contact will:

- Confirm the spec is complete
- Identify any guardrail controls needed (PII masking, HITL gate)
- Assign a Claude Code session to scaffold the implementation

---

## Step 3 — Review the Implementation PR

Claude Code will open a pull request containing:

| File                                    | What it is                     |
| --------------------------------------- | ------------------------------ |
| `automations/<name>/run.py`             | The automation script          |
| `specs/automation/<name>.md`            | Your spec (formalised)         |
| `tests/unit/automations/test_<name>.py` | Automated tests                |
| `docs/quickstart/<name>-runbook.md`     | How to run and troubleshoot it |

You will be tagged as a reviewer. Check:

- [ ] The steps match what you described in the spec
- [ ] The output goes to the right place
- [ ] Your name is listed as owner
- [ ] The rollback procedure is documented

You do **not** need to review the Python code itself — that is the engineer's job.
If the behaviour doesn't match your intent, comment on the PR and the engineer will adjust.

---

## Step 4 — HITL Approval for First Production Run

Any automation with external effects (file writes, API calls, notifications) requires
your explicit approval before the first production run via the HITL operator UI.

You will receive a notification with:

```
Automation: <name>
Trigger: <scheduled / manual>
Action: <plain-language description of what it will do>
Risk level: low / medium
```

Read the action summary carefully, then click **Approve** or **Reject**.

After a successful first run, low-risk automations can be promoted to **HOTL mode**
(runs without per-run approval, but you can override at any time). Ask your engineering
contact to configure this if you want it.

---

## Step 5 — Monitor and Maintain

Once running, the automation is visible in:

| Dashboard                    | What it shows                            |
| ---------------------------- | ---------------------------------------- |
| Grafana → Agent Productivity | Run count, duration, task type           |
| GitHub Actions               | CI status on each code change            |
| Audit log                    | Every run with timestamp and output hash |

To change the automation: open a new GitHub Issue describing the change, or comment
on the original issue. Do not edit `automations/<name>/run.py` directly unless you
are an engineer — changes must go through the PR review process.

To disable it: ask your engineering contact to disable the trigger. The code is
preserved so it can be re-enabled later.

---

## Persona Note

If you are using Claude Code directly with a persona configured:

- **Legal reviewer persona** — can draft the spec and docs; cannot scaffold code
- **Ops analyst persona** — can scaffold read-only automations; HITL required for writes
- **Engineer (default)** — full implementation capability

See `.claude/personas/` for the persona definitions.

---

## Related

- `specs/automation/automation-spec-template.md` — blank spec template
- `docs/quickstart/non-engineer-automation.md` — simpler intro for first-timers
- `skills/data/data-pipeline.md` — for data-processing automations
- `CLAUDE.md §9` — hybrid workflow and personas
