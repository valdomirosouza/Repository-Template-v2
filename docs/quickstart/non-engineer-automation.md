# Non-Engineer Automation Guide

**Audience:** Product managers, legal, operations, compliance, and data analysts
**Issue:** #10 | **Skill:** `skills/sdlc/agent-onboarding.md`

You do not need to write code to automate a repetitive workflow using Claude Code.
This guide shows how to describe a workflow in plain language, let Claude scaffold
it, and safely deploy it with human oversight.

---

## What You Can Automate

Good candidates:

- Repetitive data formatting or transformation (CSV → report, PDF → structured data)
- Scheduled notification or summary generation
- Document drafting from structured inputs (contracts, memos, tickets)
- Cross-system data lookup and aggregation (read-only)

Not suitable for self-service automation (requires engineering involvement):

- Anything that modifies a production database
- Anything that sends external communications at scale (email, SMS)
- Payment or financial transaction processing
- Actions requiring access to production credentials

---

## Step 1 — Write a Workflow Spec (no code required)

Copy this template and fill it in. Aim for 1–2 sentences per section:

```markdown
# Workflow Spec: <Short Name>

**Trigger:** <What starts this workflow? A scheduled time, a file upload, a form submission?>
**Input:** <What data does it need? Where does it come from?>
**Steps:** <Numbered list of what the workflow does, in plain language>
**Output:** <What does it produce? Where does it go?>
**Guardrails:**

- Does it handle personal data (names, emails, IDs)? Yes / No
- Does it make any external calls (API, email, Slack)? Yes / No
- Who must approve before it runs in production? <Name / Role>
  **Rollback:** <How do we undo it if something goes wrong?>
  **Owner:** <Your name and role>
  **SLA:** <How quickly must it complete? How often does it run?>
```

**Example:**

```markdown
# Workflow Spec: Weekly Support Ticket Summary

Trigger: Every Monday at 08:00
Input: CSV export from Zendesk containing tickets from the previous week
Steps:

1. Read the CSV
2. Count tickets by category and priority
3. Identify any SLA breaches (resolution time > 48h)
4. Generate a Markdown summary report
   Output: Markdown file saved to /reports/weekly-summary-YYYY-MM-DD.md
   Guardrails:

- Personal data: Yes — ticket submitter names present; must be masked in the report
- External calls: No — read-only, local file output only
- Approval required: No — read-only automation
  Rollback: Delete the generated report file
  Owner: Maria Silva, Head of Support
  SLA: Must complete within 5 minutes of trigger
```

---

## Step 2 — Submit as a GitHub Issue

Create a GitHub Issue in this repository:

1. Click **New Issue** → select the **Automation Request** template (or use a blank issue)
2. Title: `feat(automation): <Short Name>`
3. Body: paste your completed workflow spec
4. Add label: `automation-request`
5. Assign to your engineering contact

A Claude Code session will read the spec and scaffold the automation — you will be
asked to review the output before it runs anywhere.

---

## Step 3 — Review the Scaffolded Automation

Claude Code will produce:

- A Python script under `automations/<name>/run.py`
- A spec file at `specs/automation/<name>.md` (based on your issue)
- A test file at `tests/unit/automations/test_<name>.py`

Before approving, verify:

| Check                   | What to look for                                             |
| ----------------------- | ------------------------------------------------------------ |
| No hardcoded values     | No usernames, passwords, or file paths baked into the script |
| No real PII in tests    | Test fixtures use fake names/emails, not real data           |
| HITL gate present       | Any automation with external effects calls the HITL gateway  |
| Rollback is implemented | The script can undo its output                               |

If anything looks wrong, comment on the PR and the engineer will adjust.

---

## Step 4 — HITL Approval for First Production Run

Any automation that has external effects (writes a file, calls an API, sends a
notification) requires your explicit approval before the first production run.

You will receive a notification through the HITL operator UI:

```
Action: run-automation/<name>
Triggered by: scheduler / manual
Risk level: low
Approve / Reject?
```

Read the action summary and click **Approve**. After the first run, low-risk automations
can be configured to run without per-run approval (HOTL mode).

---

## Safety Guardrails (always active)

Regardless of what you automate, these protections are always on:

- **PII masking** — any personal data in the input is masked before the script logs it
- **No secret access** — scripts run with a restricted permission set; no access to
  production database passwords or API keys unless explicitly granted by an engineer
- **Audit trail** — every automation run is logged with timestamp, input hash, and output
- **HITL for external effects** — any action that sends data outside the system requires
  human approval (configurable after the first successful run)

Questions? Open a GitHub Discussion or contact your engineering team.
