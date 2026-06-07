# Customising This Template

This guide walks you through adopting this repository as the foundation for a new project.
Read it after completing the [Quick Start in README.md](README.md#quick-start-clone--initial-setup--code).

---

## 1. Minimum Required Changes

> **Do it all in one command:**
> `make template-init PROJECT_NAME=<name> ORG=<org> REGISTRY=<registry> [PROFILE=python-api] [PACKAGE_ROOT=com.x]`
> performs every change in the table below — placeholder replacement, version reset,
> `.env` creation (`SETUP_COMPLETE=true`, `COMPOSE_PROJECT_NAME`), CHANGELOG reset, and
> profile-based service removal — idempotently. The table is the manual reference; run
> `make doctor` afterwards to verify.

These must be done before your first commit on a real project:

| File / directory       | What to change                                                  | Why                                                                |
| ---------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------ |
| `services.yaml`        | Rename `template-service`, update ports, topic names            | Prevents collisions with other template instances                  |
| `.env.example`         | Replace `placeholder-set-in-env` values with your real defaults | App won't start without `DATABASE_URL`, `REDIS_URL`, `LLM_API_KEY` |
| `src/shared/config.py` | Change `service_name` default                                   | Appears in all traces, metrics, and logs                           |
| `.github/CODEOWNERS`   | Set team/individual owners per directory                        | Enforces approval routing in PRs                                   |
| `version.txt`          | Reset to `0.1.0`                                                | Keeps your semver independent of the template's                    |
| `CHANGELOG.md`         | Clear existing entries; start a fresh `[Unreleased]` section    | Avoids template history polluting your changelog                   |
| `docs/adr/README.md`   | Update the ADR index header with your project name              | Cosmetic but matters for team docs                                 |

---

## 2. What to Remove If You Don't Need It

The template includes scaffolding for every language and subsystem. Remove what you won't use to reduce noise.

> **Prefer profiles over deletion for infrastructure.** Each `docker-compose.yml` service
> is tagged with a `profiles:` key (`core` / `observability` / `events` / `full`). To run
> a lighter stack, just pick a setup profile — `make setup-minimal` (no Docker),
> `make setup-core` (PostgreSQL + Redis + observability), or `make setup-full` (everything).
> You only need the `rm -rf` steps below when you want to permanently drop a language or
> subsystem from the repo.

### No Java services

```bash
# Remove Java Makefile targets (test-java, build-java, etc.) or leave them — they're no-ops without services/
rm -rf services/       # if no polyglot services planned at all
```

Remove `ci-java.yml` from `.github/workflows/` if Java CI will never run.

### No Go services

Same pattern — remove `ci-go.yml` and any Go entries in `services.yaml`.

### No frontend

```bash
rm -rf frontend/
```

Remove `ci-frontend.yml` and the `run-frontend` / `test-frontend` targets from `Makefile`.

### No multi-agent harness

Set in `.env`:

```bash
HARNESS_MODE=solo
```

You can leave `src/agents/harness/` in place — it's only loaded when `harness_mode != solo`. To remove it entirely:

```bash
rm -rf src/agents/harness/
```

Update `src/workers/request_consumer.py` to not import `HarnessCoordinator`.

### No agent memory (pgvector)

```bash
rm -rf src/memory/
```

Remove the `pgvector` extension and `agent_memory_documents` table from `alembic/versions/0002_*`. Remove the `pgvector` service from `docker-compose.yml` if running separately.

### No sandbox execution

```bash
rm src/agents/sandbox_executor.py
rm docker-compose.sandbox.yml
rm infrastructure/feature-flags/flags/sandbox-mode.yaml
```

### No HITL (all autonomous)

Only do this with explicit governance sign-off per ADR-0015. Set the `autonomous-mode-full` flag in `infrastructure/feature-flags/flags/` to `on`.

---

## 3. How to Write Your First Spec (SDD)

This repo enforces **Spec-Driven Development** — no code without a referenced spec. Here's the minimum path:

### Step 1 — Copy the spec template

```bash
cp specs/system/vision.md specs/system/my-feature.md
# or for AI work:
cp specs/ai/agent-design.md specs/ai/my-agent.md
```

### Step 2 — Fill in the required sections

Every spec needs:

```markdown
# <Feature Name>

**Status:** Draft | **Owner:** <your name> | **Last updated:** YYYY-MM-DD
**ADR references:** ADR-NNNN (if applicable)

## Problem

## Solution

## Non-Goals
```

### Step 3 — Link it to a GitHub Issue

Create an issue, paste the spec path in the description. All PRs must reference both.

### Step 4 — Reference the spec in your code

Every module that implements a spec starts with:

```python
"""<module description>

Spec: specs/system/my-feature.md
ADR:  ADR-NNNN
"""
```

---

## 4. How to Register a New Service

Full guide: [`scaffold/README.md`](scaffold/README.md) (templates, flags, file trees) and
the 10-step checklist in [`docs/quickstart/add-new-service.md`](docs/quickstart/add-new-service.md).

Quick reference — `REGISTER=true` updates `services.yaml`, `.github/CODEOWNERS`, and the
Prometheus scrape config for you:

```bash
# Scaffold AND self-register in one step:
make new-service NAME=my-service LANG=python OWNER=platform PORT=8020 REGISTER=true

# Or scaffold only, then register manually:
make new-service NAME=my-service LANG=python   # or java / go
# 1. Add entry to services.yaml (name, port, topics, owner)
# 2. Add to .github/CODEOWNERS
# 3. Add Prometheus scrape job to infrastructure/monitoring/prometheus/prometheus.yml
# 4. Edit services/my-service/README.md (purpose, runbook link, owner)
```

---

## 5. How to Choose `harness_mode`

| Your task looks like...                               | Mode         | Why                                                   |
| ----------------------------------------------------- | ------------ | ----------------------------------------------------- |
| Single, well-scoped request handled in one LLM call   | `solo`       | Lowest cost and latency                               |
| A feature with 2–5 independently testable steps, ~1 h | `simplified` | Generator + Evaluator loop catches regressions        |
| Ambiguous scope, multiple features, 2 h+              | `full`       | Planner decomposes first, avoiding mid-task surprises |

Set in `.env`:

```bash
HARNESS_MODE=solo          # default — change per deployment
```

Or override per-request by passing `harness_mode` in the request context (see `specs/ai/harness-design.md §5`).

**Cost multipliers** (relative to `solo`):

| Mode         | Typical LLM call count | Relative cost |
| ------------ | ---------------------- | ------------- |
| `solo`       | 1                      | 1×            |
| `simplified` | 3–8                    | 5–10×         |
| `full`       | 10–25                  | 15–25×        |

---

## 6. AI Behavioral Contract (`CLAUDE.md`)

`CLAUDE.md` is the authoritative behavioral contract for Claude Code in this repo. Adjust it for your team:

- **Section 1 (Identity)** — update the role description and scope
- **Section 3 (Inviolable Rules)** — add project-specific security or privacy rules
- **Section 4 (Skill Activation Table)** — add or remove skill triggers
- **Section 6 (Branch & Commit Conventions)** — align with your team's convention

Do **not** remove existing rules without a governance decision — they exist because of real incidents or regulatory obligations (see each ADR for the rationale).

---

## 7. Keeping Your Fork in Sync

This template evolves. The recommended way to pull upstream improvements is the
**`template-sync` workflow** (`.github/workflows/template-sync.yml`) — it runs weekly
(and on demand via **Actions → Template Sync → Run workflow**), fetches the template,
and opens a **draft PR** with the changed files so you can review and merge selectively.
It never overwrites your project-specific files:

`CLAUDE.md`, `CLAUDE_SESSION_INIT.md`, `services.yaml`, `.env.example`, `docs/adr/`,
`specs/`, `CHANGELOG.md`, `.github/CODEOWNERS`, `AGENTS.md`.

The workflow expects a `template` remote pointing at the upstream template; the workflow
adds it automatically. No manual `git merge --allow-unrelated-histories` is needed.

---

## 8. Agentic SDLC — Progressive Adoption Guide

The 13-phase Agentic SDLC (ADR-0052) is designed for progressive adoption. Start with what provides value now and expand as your team grows. **Full reference:** `docs/process/WORKFLOW.md`.

### Tier 0 — Solo / 1–5 Engineers

**Activate:**

| Item                                    | How                                                                  |
| --------------------------------------- | -------------------------------------------------------------------- |
| GitHub Issues with basic labels         | Enable via `.github/labels.yml`                                      |
| `docs/process/DEFINITION_OF_DONE.md`    | Use as PR checklist reference                                        |
| Sprint Board (Projects View 2 only)     | Create a single Projects board                                       |
| Bi-weekly retrospective (async, 15 min) | Use sprint retro template from `docs/process/RETROSPECTIVE-GUIDE.md` |
| CI gates: lint + unit tests             | `ci.yml` runs automatically                                          |

**Skip for now:**

- Grooming Ceremony → ad-hoc Issue triage
- Formal DoR checklist → informal review in Issue comments
- Release retrospective → sprint retro covers it
- CAB / RFC process → Tech Lead solo approval
- HITL runtime gateway → solo projects may use `LOW_RISK` autonomy level (still log all actions)

**Process phases to activate:** 1 (Conception) → 6 (Development) → 7 (Code Review) → 8 (Testing) → 12 (Production deploy)

---

### Tier 1 — Small Team / 6–20 Engineers

**Activate (in addition to Tier 0):**

| Item                                       | How                                                |
| ------------------------------------------ | -------------------------------------------------- |
| Full 5-view Projects board                 | Import `.github/project-board-definition.json`     |
| Weekly Grooming Ceremony                   | 60 min; DoR checklist enforced                     |
| `docs/process/DEFINITION_OF_READY.md`      | DoR enforced at Grooming                           |
| Spec-as-PR for `discovery.md` and `nfr.md` | Phase 2 discovery workflow                         |
| Feature spec template                      | `specs/features/FEAT-{id}/feature-spec.md`         |
| `docs/process/HITL-GOVERNANCE.md`          | Tier 1 (Spec-as-PR) governance                     |
| Release retrospective                      | Per-release; 60–90 min                             |
| `docs/process/DEFINITION_OF_RELEASE.md`    | DoR-Release checklist before every release         |
| HITL runtime gateway (default `NONE`)      | Enabled by default in `src/agents/hitl_gateway.py` |

**Skip for now:**

- CAB for Standard Changes → Tech Lead approval sufficient
- Formal PRR → SRE checklist in PR description
- SOX controls → unless SEC-listed

**Additional phases to activate:** 2 (Discovery) → 3 (Grooming) → 4 (Specification) → 11 (Release RC) → 13 (Post-Deploy)

---

### Tier 2 — Medium Team / 21–50 Engineers

**Activate (in addition to Tier 1):**

| Item                                                  | How                                                           |
| ----------------------------------------------------- | ------------------------------------------------------------- |
| Full CAB for Normal and Emergency changes             | `skills/compliance/iso27001-change-management.md`             |
| Formal PRR (`skills/sre/prr.md`) for all new services | Required before Phase 12                                      |
| Security Debt view (Projects View 3)                  | Security Lead reviews weekly                                  |
| `docs/process/RACI.md`                                | Ownership clarity as team grows                               |
| DORA Dashboard (Projects View 5 + Grafana)            | `infrastructure/monitoring/grafana/dora-metrics.json`         |
| Monthly DORA report                                   | `docs/sre/dora-report-YYYY-MM.md` template                    |
| Abuse case tests                                      | `make test-abuse-cases` blocking gate                         |
| Model contract tests                                  | `pytest tests/model_contract/ -m model_contract` on model PRs |
| `docs/process/SPRINT-TRACKING.md`                     | Full sprint governance                                        |

**Skip for now:**

- SOX controls → unless SEC-listed
- Dedicated Release Manager role → Tech Lead covers it

**Additional phases to activate:** 5 (Architecture) → 9 (DevSecOps) → 10 (Observability/PRR)

---

### Tier 3 — Large Team / 50+ Engineers

**Activate (in addition to Tier 2):**

| Item                                         | How                                                                           |
| -------------------------------------------- | ----------------------------------------------------------------------------- |
| SOX controls (if SEC-listed)                 | `skills/compliance/sox.md` + `specs/compliance/sox-controls.md`               |
| Dedicated Release Manager role               | Assign ownership per `docs/process/RACI.md` Tier 5                            |
| Governance Council formal review             | DoD/DoR changes require council sign-off                                      |
| Full DORA Elite tracking with retrospectives | Monthly DORA report mandatory; miss triggers formal retrospective             |
| Multi-team sprint synchronisation            | Align sprint boundaries across services; use release milestones               |
| Adversarial testing                          | `tests/model_contract/` extended; red-team exercises per ADR-0050             |
| Full Secure-by-Design stack active           | All Waves 21–25 components (`src/guardrails/`, harness, behavioral contracts) |

**All 13 phases fully active.**

---

### Adoption Checklist (copy into your first setup Issue)

```markdown
## Agentic SDLC Adoption Checklist

### Tier 0 (all teams)

- [ ] GitHub labels configured (`.github/labels.yml`)
- [ ] `docs/process/DEFINITION_OF_DONE.md` linked in PR template
- [ ] Sprint Board created in GitHub Projects
- [ ] CI gates running (lint + unit tests)
- [ ] First sprint retrospective scheduled

### Tier 1 (6–20 engineers)

- [ ] All 5 Projects board views created
- [ ] Grooming Ceremony recurring calendar invite sent
- [ ] `docs/process/DEFINITION_OF_READY.md` shared with team
- [ ] Feature spec template introduced
- [ ] First release retrospective scheduled

### Tier 2 (21–50 engineers)

- [ ] CAB process documented in `docs/change-management/`
- [ ] PRR checklist embedded in new-service runbook
- [ ] Grafana DORA dashboard deployed
- [ ] Abuse case tests added to CI blocking gates
- [ ] RACI matrix reviewed and signed off by leads

### Tier 3 (50+ engineers)

- [ ] SOX applicability confirmed (or documented as N/A)
- [ ] Release Manager role assigned and documented
- [ ] Governance Council charter defined
- [ ] Red-team exercise schedule established
```

---

## 15. Running Multiple Template Instances

Several projects cloned from this template can run on the same machine without
container/port collisions:

1. **Namespace the stack.** Set a unique `COMPOSE_PROJECT_NAME` per project in `.env`
   (`make template-init` does this automatically). The Docker network and container
   names are derived from it, so two clones never clash:

   ```env
   COMPOSE_PROJECT_NAME=my-project
   ```

2. **Override conflicting ports.** Uncomment and change the port variables in `.env` —
   `docker-compose.yml` reads them with fallbacks:

   ```env
   POSTGRES_PORT=5433
   REDIS_PORT=6380
   GRAFANA_PORT=3002
   ```

3. **Verify.** `docker compose config` will show the resolved project name and ports;
   `make doctor` warns about any port already in use.
