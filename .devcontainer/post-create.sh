#!/usr/bin/env bash
# .devcontainer/post-create.sh
# Runs once after the devcontainer is created.
# Sets up all language toolchains and verifies the environment is ready.
set -euo pipefail

echo "==> [post-create] Starting environment setup..."

# ── Python ──────────────────────────────────────────────────────────────────
echo "==> [Python] Installing uv and syncing dependencies..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"
uv sync
echo "    Python OK — $(python --version)"

# ── Node / pnpm ──────────────────────────────────────────────────────────────
echo "==> [Node] Installing pnpm..."
npm install -g pnpm@9
echo "    Node OK — $(node --version), pnpm $(pnpm --version)"

# ── Go tools ─────────────────────────────────────────────────────────────────
echo "==> [Go] Installing development tools..."
go install github.com/air-verse/air@latest          # hot-reload
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
echo "    Go OK — $(go version)"

# ── Java ─────────────────────────────────────────────────────────────────────
echo "==> [Java] Verifying Maven install..."
mvn --version
echo "    Java OK — $(java --version | head -1)"

# ── Pre-commit hooks ─────────────────────────────────────────────────────────
echo "==> [git] Installing pre-commit hooks..."
if command -v pre-commit &>/dev/null; then
    pre-commit install
else
    uv run pre-commit install
fi

# ── Environment file ─────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo "==> [env] Copying .env.example → .env (edit before running services)"
    cp .env.example .env
fi

# ── Shared infrastructure ────────────────────────────────────────────────────
echo "==> [docker] Starting shared infrastructure (PostgreSQL, Redis, Kafka, OTel)..."
docker compose up -d
echo "    Waiting for PostgreSQL to be ready..."
until docker compose exec -T postgres pg_isready -q 2>/dev/null; do
    sleep 2
done

# ── Database migrations ───────────────────────────────────────────────────────
echo "==> [alembic] Running database migrations..."
uv run alembic upgrade head

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║        Environment setup complete — ready to code!        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "  Quick reference:"
echo "    make test-python          — run Python tests"
echo "    make test-java            — run Java tests (SERVICE=<name>)"
echo "    make test-go              — run Go tests"
echo "    make test-frontend        — run frontend tests"
echo "    make run                  — start Python API gateway"
echo "    make lint-python          — ruff + mypy"
echo ""
echo "  Infrastructure:"
echo "    Grafana   → http://localhost:3001  (admin/admin)"
echo "    Jaeger    → http://localhost:16686"
echo "    Prometheus→ http://localhost:9090"
echo ""
echo "  Next step: edit .env with your ANTHROPIC_API_KEY and SECRET_KEY"
echo ""
