---
name: run-repository-template
description: Run, start, launch, smoke-test, or verify the Repository-Template FastAPI server. Use this skill when asked to run the app, check endpoints, start the server, test the API, screenshot the Swagger UI, or confirm a change works in the running server.
---

# Run skill — Repository-Template FastAPI server

The app is a **Python/FastAPI server** (port 8000) with an async request pipeline and optional AI-Agents extension. It starts cleanly without Docker: Redis, Kafka, and DB all fall back to in-memory stores automatically.

The agent path is the smoke driver at `.claude/skills/run-repository-template/smoke.sh`. It launches the server, exercises every key endpoint, and stops it. All commands below were verified in this repo on 2026-06-01.

---

## Prerequisites

```bash
uv --version   # must be ≥ 0.11
```

Install `uv` if missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`

No other system packages needed. No Docker required for the smoke path.

---

## Build (deps)

```bash
uv sync
```

First run takes ~30 s; subsequent runs are instant if `pyproject.toml` hasn't changed.

---

## Run — agent path (smoke driver)

```bash
bash .claude/skills/run-repository-template/smoke.sh
```

Runs all 7 checks and exits 0 on success:

```
[smoke] PASS  GET /health → ok
[smoke] PASS  GET /ready → 503 (200=full infra, 503=in-memory fallback)
[smoke] PASS  GET /docs → Swagger HTML
[smoke] PASS  GET /metrics → Prometheus text
[smoke] PASS  GET /v1/hitl/status → operational
[smoke] PASS  POST /v1/requests → 202 queued
[smoke] PASS  GET /v1/requests/{id} → has request_id
[smoke] Results: 7 passed, 0 failed
```

Use `--keep` to leave the server running after checks:

```bash
bash .claude/skills/run-repository-template/smoke.sh --keep
# → prints PID and port; stop with: kill <PID>
```

---

## Run — human path

```bash
SECRET_KEY="dev-only-not-a-real-secret-key-xx" APP_ENV=development \
  uv run uvicorn src.api.rest.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Prometheus metrics: http://localhost:8000/metrics/ ← note trailing slash
- Stop: `Ctrl-C`

---

## Key endpoints (all confirmed working)

| Endpoint            | Method | Notes                                                             |
| ------------------- | ------ | ----------------------------------------------------------------- |
| `/health`           | GET    | Liveness — always 200                                             |
| `/ready`            | GET    | Readiness — 200 with DB, **503 without** (correct without Docker) |
| `/docs`             | GET    | Swagger UI — development only                                     |
| `/metrics/`         | GET    | Prometheus text (note: `/metrics` → 307 → `/metrics/`)            |
| `/v1/requests`      | POST   | `{"request_text":"…","priority":"normal\|low\|high"}` → 202       |
| `/v1/requests/{id}` | GET    | Poll for status                                                   |
| `/v1/hitl/status`   | GET    | HITL gateway health                                               |

---

## Gotchas

- **`/metrics` redirects** — the Prometheus mount is at `/metrics/`; plain `/metrics` returns a 307. Use `curl -L` or hit `/metrics/` directly.
- **`/ready` returns 503 without Docker** — this is correct. The readiness probe checks for a live DB pool. Without Postgres running, it 503s. Liveness (`/health`) is always 200.
- **`set -e` + arithmetic counters** — bash `((VAR++))` exits 1 when VAR is 0 (zero is falsy). The smoke driver uses `VAR=$((VAR+1))` to avoid this.
- **Port 8000 already in use** — if a previous run left the server alive, `pkill -f "uvicorn src.api.rest.main"` clears it.
- **`SECRET_KEY` length** — the production validator requires ≥ 32 chars and rejects `"placeholder"`. In development (`APP_ENV=development`) this check is skipped. Use any 32-char string for local runs.
- **Structured JSON log lines appear on stdout** — the `{"timestamp":…}` lines for submitted requests are intentional audit log output, not errors.

---

## Troubleshooting

| Symptom                              | Fix                                                          |
| ------------------------------------ | ------------------------------------------------------------ |
| `[Errno 48] address already in use`  | `pkill -f "uvicorn src.api.rest.main"`                       |
| `ModuleNotFoundError` on start       | `uv sync` (venv was deleted or corrupted)                    |
| `.venv` init error on `uv sync`      | `rm -rf .venv && uv sync`                                    |
| `/ready` returns 503                 | Expected without Postgres — not a bug                        |
| Smoke script exits after first check | `((VAR++))` under `set -e` — already fixed in current driver |
