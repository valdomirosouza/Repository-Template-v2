# Local Development Environment Setup

This guide covers prerequisites, IDE setup, the devcontainer option, and solutions to common setup errors. Read this before your language-specific quickstart guide.

---

## Option A: Devcontainer (recommended — zero prerequisite installation)

The repository ships with a fully configured devcontainer at `.devcontainer/`. It installs all runtimes, tools, and infrastructure automatically.

**Requirements:** Docker Desktop + VS Code with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers), or GitHub Codespaces.

```bash
# VS Code: open the repo folder, then accept the "Reopen in Container" prompt
# Codespaces: click "Code" → "Open with Codespaces" on the GitHub UI
```

The `post-create.sh` script runs automatically and:

- Installs Python 3.12 (uv), Node 20 (pnpm), Go 1.23, Java 21 (Maven 3.9)
- Installs all Go dev tools (`air`, `golangci-lint`, `protoc-gen-go`)
- Installs pre-commit hooks
- Copies `.env.example` → `.env`
- Starts the full infrastructure stack via `docker compose up -d`
- Runs Alembic migrations

After the container starts, set `ANTHROPIC_API_KEY` and `SECRET_KEY` in `.env` and run `make test-unit-python` to verify.

Ports forwarded automatically: `3000` (Frontend), `8000` (API Gateway), `8080` (Java), `8090` (Go), `5432` (PostgreSQL), `6379` (Redis), `9092` (Kafka), `16686` (Jaeger), `3001` (Grafana), `9090` (Prometheus).

---

## Option B: Local installation

### Required tool versions

| Tool                        | Minimum version | Install                                                   |
| --------------------------- | --------------- | --------------------------------------------------------- |
| Docker (with Compose V2)    | 24.0            | [docs.docker.com](https://docs.docker.com/get-docker/)    |
| Python                      | 3.13            | [python.org](https://python.org) or `pyenv`               |
| uv (Python package manager) | 0.4             | `curl -LsSf https://astral.sh/uv/install.sh \| sh`        |
| Java (JDK)                  | 21              | `sdk install java 21` via [sdkman.io](https://sdkman.io)  |
| Maven                       | 3.9             | `sdk install maven`                                       |
| Go                          | 1.23            | [go.dev/dl](https://go.dev/dl/)                           |
| Node.js                     | 20              | `nvm install 20` via [nvm](https://github.com/nvm-sh/nvm) |
| pnpm                        | 9               | `npm install -g pnpm@9`                                   |

You only need Java/Maven if working on Java services, Go if working on Go services, and Node/pnpm if working on the frontend. Python + Docker are always required.

### Verify your install

```bash
python --version      # 3.13.x
uv --version          # 0.4.x or later
docker compose version  # v2.x.x
go version            # go1.23.x
java --version        # 21.x.x
node --version        # v20.x.x
```

### First-time setup

```bash
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY and SECRET_KEY (see CUSTOMISING.md §1 Minimum Required Changes)

make infra-up         # start PostgreSQL, Redis, Kafka, Schema Registry, OTel, Grafana, flagd
make setup            # uv sync + Alembic migrations
make test-unit-python # verify baseline (no Docker needed for unit tests)
make lint-python      # ruff + mypy + detect-secrets
```

---

## IDE extensions

### VS Code (pre-configured in devcontainer)

The devcontainer installs these automatically. For local installs, add them manually:

| Extension         | ID                            |
| ----------------- | ----------------------------- |
| Python            | `ms-python.python`            |
| Mypy type checker | `ms-python.mypy-type-checker` |
| Ruff              | `charliermarsh.ruff`          |
| Java Pack         | `vscjava.vscode-java-pack`    |
| Go                | `golang.go`                   |
| ESLint            | `dbaeumer.vscode-eslint`      |
| Prettier          | `esbenp.prettier-vscode`      |
| Docker            | `ms-azuretools.vscode-docker` |
| REST Client       | `humao.rest-client`           |
| YAML              | `redhat.vscode-yaml`          |

### IntelliJ IDEA / JetBrains

Recommended plugins: Python, Go, Docker, OpenTelemetry, Kafka (Kafkalytic).

---

## Common setup errors and fixes

### `docker compose up` fails — port already in use

Check which process owns the conflicting port and stop it, or change the port in `.env`:

```bash
lsof -i :5432   # find what's using PostgreSQL port
# If it's a local PostgreSQL: brew services stop postgresql
```

Common conflicts: PostgreSQL (5432), Redis (6379), Kafka (9092).

### `uv sync` fails — Python version mismatch

The project requires Python 3.13+. If your system Python is older:

```bash
pyenv install 3.13
pyenv local 3.13
uv sync
```

### `alembic upgrade head` fails — database not ready

The PostgreSQL container may not be ready yet. Wait 5 seconds and retry:

```bash
until docker compose exec postgres pg_isready -q; do sleep 2; done
uv run alembic upgrade head
```

### `make test-python` fails with `Connection refused` on Redis/Kafka

Integration tests require the test infrastructure stack, not the dev stack:

```bash
make test-infra-up          # starts test stack with offset ports
uv run pytest tests/integration/ -v
make test-infra-down
```

Unit tests (`make test-unit-python`) never need Docker.

### Kafka fails to start — `Invalid cluster.id`

The KRaft cluster ID is fixed in `docker-compose.yml`. If you've run the container before with a different ID, wipe the volume:

```bash
make infra-reset   # stops containers AND wipes all volumes
make infra-up
```

### `detect-secrets scan` reports a finding in my code

The baseline is at `.secrets.baseline`. If it's a false positive, add it to the baseline:

```bash
uv run detect-secrets scan --update .secrets.baseline
git add .secrets.baseline
```

If it's a real secret: remove it, rotate the credential immediately, and do not commit it.

### `mypy` reports errors after adding a new dependency

Run `uv add <package>` to install the package and its type stubs:

```bash
uv add httpx          # installs package
uv add --dev types-httpx  # installs stubs if available
uv run mypy src/
```

### Pre-commit hook blocks my commit

Pre-commit runs ruff, mypy, and detect-secrets before every commit. If it fails:

```bash
uv run pre-commit run --all-files   # see all failures at once
uv run ruff format src/ tests/      # auto-fix formatting
```

Do not use `git commit --no-verify`. Hooks are a safety control, not an inconvenience.

---

## Observability stack (available after `make infra-up`)

| Service               | URL                    | Default credentials |
| --------------------- | ---------------------- | ------------------- |
| Grafana (dashboards)  | http://localhost:3001  | admin / admin       |
| Jaeger (traces)       | http://localhost:16686 | —                   |
| Prometheus (metrics)  | http://localhost:9090  | —                   |
| Schema Registry       | http://localhost:8081  | —                   |
| flagd (feature flags) | http://localhost:8014  | —                   |

---

## Next steps

Once your environment is healthy, open your language-specific quickstart:

- Python: [`python-backend.md`](python-backend.md)
- Java: [`java-backend.md`](java-backend.md)
- Go: [`go-backend.md`](go-backend.md)
- Frontend: [`frontend.md`](frontend.md)
- Batch jobs: [`jobs-worker.md`](jobs-worker.md)
