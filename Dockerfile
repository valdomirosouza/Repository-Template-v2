# syntax=docker/dockerfile:1.7
# Multi-stage build — target "production" is used by make build and CI.

# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Use the floating slim tag so OS-level security patches are picked up
# automatically. Patch-level pinning (python:3.13.x-slim) locks you to a
# specific OS image that may carry unfixed CVEs; use digest pinning via a bot
# (e.g. Renovate) that also runs a security scan before merging the update.
FROM python:3.13-slim AS builder

WORKDIR /build

# Install uv for fast, reproducible dependency installation
COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /usr/local/bin/uv

# Copy dependency manifests first to maximise layer cache reuse
COPY pyproject.toml ./
COPY uv.lock* ./

# Install production dependencies into /build/.venv
RUN uv sync --no-dev --frozen

# Copy source after deps to avoid busting cache on code changes
COPY src/ ./src/

# ── Stage 2: production ───────────────────────────────────────────────────────
FROM python:3.13-slim AS production

# Security: run as non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Copy only the built venv and source — no build tools, no dev deps
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src /app/src

# Ensure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

USER appuser

EXPOSE 8000

# Healthcheck aligned with smoke-test.sh endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

STOPSIGNAL SIGTERM
ENTRYPOINT ["uvicorn", "src.api.rest.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
