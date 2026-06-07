# Troubleshooting

The 15 most common first-run failures and how to self-serve. Run `make doctor` first —
it detects most of these automatically.

---

### 1. Docker not running

**Symptom:** `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`.
**Likely cause:** Docker Desktop / Colima isn't started.
**Confirm:** `docker info`
**Fix:** Start Docker Desktop (or `colima start`), then re-run `make setup-core`.

### 2. Port already in use

**Symptom:** `Bind for 0.0.0.0:5432 failed: port is already allocated`.
**Likely cause:** Another PostgreSQL/Redis (or another template clone) holds the port.
**Confirm:** `lsof -iTCP:5432 -sTCP:LISTEN`
**Fix:** Stop the other service, or override the port in `.env` (`POSTGRES_PORT=5433`) — see `CUSTOMISING.md` §15.

### 3. Python version mismatch

**Symptom:** `requires-python >=3.13` / uv refuses to sync.
**Likely cause:** Active Python is < 3.13.
**Confirm:** `make check-versions`
**Fix:** `uv python install 3.13 && uv sync`.

### 4. Node version mismatch

**Symptom:** `error … engine "node" is incompatible … Expected >=22`.
**Likely cause:** Node < 22.
**Confirm:** `node --version`
**Fix:** `nvm install 22 && nvm use 22`.

### 5. Go version mismatch

**Symptom:** `go.mod requires go >= 1.24`.
**Likely cause:** Go toolchain < 1.24.
**Confirm:** `go version`
**Fix:** Install Go 1.24+ from https://go.dev/dl.

### 6. `.env` missing

**Symptom:** Startup error from `Settings` / `reject_placeholder_secrets`.
**Likely cause:** No `.env` file.
**Confirm:** `test -f .env || echo missing`
**Fix:** `cp .env.example .env` (or run `make template-init …`, which does it for you).

### 7. `SECRET_KEY` still a placeholder

**Symptom:** App refuses to start in production: `SECRET_KEY must be set …`.
**Likely cause:** `SECRET_KEY` left as a placeholder.
**Confirm:** `grep ^SECRET_KEY= .env`
**Fix:** `openssl rand -hex 32`, then set `SECRET_KEY` in `.env` (≥ 32 chars).

### 8. PostgreSQL not ready

**Symptom:** `GET /ready` returns `503`.
**Likely cause:** PostgreSQL still initialising or not started.
**Confirm:** `pg_isready -h localhost -p 5432` / `docker compose ps`
**Fix:** Wait for the healthcheck, or `make setup-core` to (re)start it.

### 9. Redis requires a password

**Symptom:** `NOAUTH Authentication required`.
**Likely cause:** `REDIS_URL` lacks the password the container expects.
**Confirm:** `grep ^REDIS_URL= .env`
**Fix:** Use `redis://:<password>@localhost:6379/0` matching `REDIS_PASSWORD`.

### 10. Kafka slow startup

**Symptom:** Schema Registry health check fails right after `make setup-full`.
**Likely cause:** Kafka (KRaft) needs ~30s before Schema Registry can connect.
**Confirm:** `docker compose logs kafka | tail`
**Fix:** Wait for Kafka to become healthy, then it self-recovers; re-run `make smoke`.

### 11. CODEOWNERS placeholders not replaced

**Symptom:** CI governance fails on `@org/` placeholder teams.
**Likely cause:** Template not initialised.
**Confirm:** `grep '@your-org/' .github/CODEOWNERS`
**Fix:** `make template-init PROJECT_NAME=… ORG=… REGISTRY=…` (or replace handles manually).

### 12. GitHub teams do not exist

**Symptom:** Reviewer auto-assignment silently does nothing.
**Likely cause:** CODEOWNERS references teams/handles that don't exist in your org.
**Confirm:** Open a PR and check the requested reviewers.
**Fix:** Edit `.github/CODEOWNERS` to real usernames/teams; see `docs/governance/owner-onboarding.md`.

### 13. AI API key not configured

**Symptom:** Agent actions route to HITL unexpectedly, or startup errors with AI enabled.
**Likely cause:** `AI_AGENTS_ENABLED=true` but no `LLM_API_KEY`.
**Confirm:** `grep -E '^AI_AGENTS_ENABLED|^LLM_API_KEY' .env`
**Fix:** Set `LLM_API_KEY` (or the `ANTHROPIC_API_KEY` alias), or set `AI_AGENTS_ENABLED=false`.

### 14. Devcontainer Python/Node mismatch

**Symptom:** `uv: command not found` or wrong runtime in the devcontainer.
**Likely cause:** Stale devcontainer image from before the toolchain bump.
**Confirm:** `make check-versions`
**Fix:** Rebuild: **Dev Containers: Rebuild Container** (uses Python 3.13 / Node 22 / Go 1.24).

### 15. `make doctor` fails on Java

**Symptom:** `doctor` warns Java is missing or version undetectable.
**Likely cause:** No JDK, or `JAVA_HOME` unset (the macOS `java` stub has no runtime).
**Confirm:** `java -version`
**Fix:** `sdk install java 21-tem` and set `JAVA_HOME`. Java is optional — ignore if you don't build Java services.
