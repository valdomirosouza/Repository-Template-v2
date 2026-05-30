# Customising This Template

This guide walks you through adopting this repository as the foundation for a new project.
Read it after completing the [5-step setup in README.md](README.md#5-step-setup).

---

## 1. Minimum Required Changes

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

Full 10-step checklist: [`docs/quickstart/add-new-service.md`](docs/quickstart/add-new-service.md)

Quick reference:

```bash
# Scaffold the service
make new-service NAME=my-service LANG=python   # or java / go

# Then:
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

This template evolves. To pull upstream improvements without overwriting your changes:

```bash
git remote add template https://github.com/valdomirosouza/Repository-Template.git
git fetch template
git merge template/main --allow-unrelated-histories --no-commit
# Resolve conflicts — keep your project-specific files, take template improvements
git commit -m "chore: sync from template vX.Y.Z"
```

Files you should almost always keep from **your** version (don't overwrite):
`CLAUDE.md`, `.env.example`, `services.yaml`, `docs/adr/`, `specs/`, `CHANGELOG.md`, `CODEOWNERS`.
