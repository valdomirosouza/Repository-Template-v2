# First-Run Setup Checklist

> **Step 0 — fastest path:** run `make template-init PROJECT_NAME=<name> ORG=<org> REGISTRY=<registry> [PROFILE=python-api]`
> to perform Steps 1–4 below in one idempotent command, then `make doctor` to validate.
> The steps below remain as the manual/verification reference.
>
> If you created this repo with GitHub's **"Use this template"** button, the
> `template-init` workflow (`.github/workflows/template-init.yml`) fires automatically on
> the first push to `main` and opens a `chore: initial project customisation` PR for you —
> review it, complete the 3 manual steps in its body, then merge.

Complete these steps **before opening your first PR**. Steps 1–3 are enforced by CI gates and will block every merge until done. Steps 4–6 are strongly recommended before inviting collaborators.

> **Note:** the CODEOWNERS and placeholder governance checks are **automatically skipped**
> until the template is initialised (until `@your-org/`/`yourorg/` placeholders are
> replaced). A fresh "Use this template" clone will not fail CI on day zero; it gets a
> reminder annotation instead. Once `make template-init` has run, the checks enforce normally.

---

## Step 1 — Replace CODEOWNERS teams `[CI BLOCKER]`

**File:** `.github/CODEOWNERS`

Every line references `@your-org/<role>` placeholder teams. The `pr-governance` workflow will fail every PR with:

```
CODEOWNERS contains unresolved @org/ placeholder teams.
These patterns silently fail GitHub reviewer auto-assignment.
```

**Action:** Replace each `@your-org/<role>` with a real GitHub username or team handle.

```
# Before
src/                  @your-org/backend-engineers

# After
src/                  @acme/backend-engineers   # or @alice @bob
```

See `docs/governance/owner-onboarding.md` for the full role-to-team mapping guide.

---

## Step 2 — Replace image registry in `services.yaml` `[CI BLOCKER]`

**File:** `services.yaml`

Every service entry has `image: yourorg/<service-name>`. Helm deploys and container pushes will fail with the wrong registry.

**Action:** Replace `yourorg` with your actual container registry org on all five image fields:

```yaml
# Before
image: yourorg/api-gateway

# After
image: acme/api-gateway          # Docker Hub
# OR
image: ghcr.io/acme/api-gateway  # GitHub Container Registry
# OR
image: 123456789.dkr.ecr.us-east-1.amazonaws.com/api-gateway  # AWS ECR
```

Services to update: `api-gateway`, `domain-service`, `event-worker`, `frontend`, `batch-jobs`.

---

## Step 3 — Set `[REQUIRED]` values in `.env` `[APP BLOCKER]`

**File:** `.env` (copy of `.env.example`)

The application refuses to start in staging/production if placeholder secrets are detected (`Settings.reject_placeholder_secrets`).

```bash
cp .env.example .env
```

Minimum required values (marked `[REQUIRED]` in `.env.example`):

| Variable            | How to generate        | Used for                                                                                                                       |
| ------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `SECRET_KEY`        | `openssl rand -hex 32` | JWT signing                                                                                                                    |
| `DB_ENCRYPTION_KEY` | `openssl rand -hex 32` | AES-256-GCM column encryption                                                                                                  |
| `LLM_API_KEY`       | console.anthropic.com  | **Required only when `AI_AGENTS_ENABLED=true`** — leave placeholder otherwise (`ANTHROPIC_API_KEY` is a backward-compat alias) |

> `REDIS_TLS_ENABLED` and `PAGERDUTY_INTEGRATION_KEY` are required for production but not for local dev.

---

## Step 4 — Reset version `[RECOMMENDED]`

**Files:** `version.txt`, `pyproject.toml`, `README.md`, `CLAUDE.md`

Reset to `0.1.0` before your first commit so your release history starts clean.

```bash
# version.txt
echo "0.1.0" > version.txt

# pyproject.toml
sed -i '' 's/version = "1\.26\.[0-9]*"/version = "0.1.0"/' pyproject.toml
```

Also update the `**Version:**` header in `README.md` and `CLAUDE.md`.

---

## Step 5 — Configure CI registry credentials `[RECOMMENDED]`

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

| Secret              | Value                                    |
| ------------------- | ---------------------------------------- |
| `REGISTRY_USERNAME` | Your container registry username         |
| `REGISTRY_PASSWORD` | Your container registry token / password |

Add these variables (Settings → Variables):

| Variable             | Value                               |
| -------------------- | ----------------------------------- |
| `CONTAINER_REGISTRY` | e.g. `ghcr.io` or `docker.io`       |
| `STAGING_BASE_URL`   | e.g. `https://api.staging.acme.com` |

Without these, the `cd-staging` and `cd-production` pipelines will fail at the login step.

---

## Step 6 — Customise or remove optional extensions `[OPTIONAL]`

See [`CUSTOMISING.md`](CUSTOMISING.md) for the full adoption guide:

- **Remove AI Agents** — delete `src/agents/`, `src/guardrails/`, `src/memory/` if you don't need HITL/HOTL
- **Remove Java service** — delete `services/domain-service/` and remove from `services.yaml`
- **Remove Go worker** — delete `services/event-worker/` and remove from `services.yaml`
- **Remove frontend** — delete `frontend/` and remove from `services.yaml`
- **Remove Terraform** — delete `infrastructure/terraform/` if you manage infra separately

---

## Verification

**Recommended: validate your environment first.** After the steps above (and after
`make template-init` once available), run the doctor — it checks your toolchain, `.env`,
ports, and unresolved placeholders, and tells you exactly what to fix:

```bash
make doctor        # validate tools, .env, ports, placeholders
make check-versions  # confirm runtime versions meet the minimums
```

Then open a test PR to confirm:

```bash
# Step 1 — governance check should pass
# Step 2 — contract-drift check should pass
# Step 3 — app should start cleanly
make run
curl http://localhost:8000/ready   # → {"status": "ready"}
```

Hit a snag? See [`docs/troubleshooting.md`](docs/troubleshooting.md) — the 15 most common
first-run failures with confirm/fix steps.
