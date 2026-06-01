#!/usr/bin/env bash
# smoke.sh — launch the FastAPI server, run all smoke checks, then stop it.
# Usage: bash .claude/skills/run-repository-template/smoke.sh [--keep]
# --keep  leave the server running after checks (prints PID)
#
# Requires: uv (https://github.com/astral-sh/uv) — installs deps if .venv absent.
# No Docker required: Redis/Kafka/DB all fall back to in-memory stores.

set -euo pipefail

PORT=8000
KEEP=false
[[ "${1:-}" == "--keep" ]] && KEEP=true

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

# ── 1. Deps ───────────────────────────────────────────────────────────────────
if [[ ! -d .venv ]]; then
  echo "[smoke] Installing dependencies (first run)..."
  uv sync --quiet
fi

# ── 2. Start server ───────────────────────────────────────────────────────────
echo "[smoke] Starting server on :$PORT..."
SECRET_KEY="dev-only-not-a-real-secret-key-xx" \
APP_ENV=development \
  uv run uvicorn src.api.rest.main:app \
    --port "$PORT" --no-access-log \
    --log-level warning &
SERVER_PID=$!

# Wait for server to accept connections (up to 15 s)
for i in $(seq 1 30); do
  if curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
  if [[ $i -eq 30 ]]; then echo "[smoke] FAIL: server did not start in 15 s"; kill $SERVER_PID 2>/dev/null; exit 1; fi
done

PASS=0; FAIL=0
check() {
  local label="$1"; local result="$2"; local expected="$3"
  if echo "$result" | grep -q "$expected"; then
    echo "[smoke] PASS  $label"
    PASS=$((PASS+1))
  else
    echo "[smoke] FAIL  $label — got: $result"
    FAIL=$((FAIL+1))
  fi
}

# ── 3. Health ─────────────────────────────────────────────────────────────────
check "GET /health → ok" \
  "$(curl -sf http://localhost:$PORT/health)" '"status":"ok"'

# ── 4. Ready (503 expected without DB — that is correct behaviour) ─────────────
READY_CODE=$(curl -so /dev/null -w "%{http_code}" http://localhost:$PORT/ready)
if [[ "$READY_CODE" == "200" || "$READY_CODE" == "503" ]]; then
  echo "[smoke] PASS  GET /ready → $READY_CODE (200=full infra, 503=in-memory fallback)"
  PASS=$((PASS+1))
else
  echo "[smoke] FAIL  GET /ready → unexpected $READY_CODE"
  FAIL=$((FAIL+1))
fi

# ── 5. Swagger UI ─────────────────────────────────────────────────────────────
check "GET /docs → Swagger HTML" \
  "$(curl -sf http://localhost:$PORT/docs | head -c 200)" 'swagger\|SwaggerUI\|<!DOCTYPE'

# ── 6. Metrics ────────────────────────────────────────────────────────────────
check "GET /metrics → Prometheus text" \
  "$(curl -sfL http://localhost:$PORT/metrics | head -3)" '# HELP\|# TYPE\|python_'

# ── 7. HITL status ────────────────────────────────────────────────────────────
check "GET /v1/hitl/status → operational" \
  "$(curl -sf http://localhost:$PORT/v1/hitl/status)" '"status":"operational"'

# ── 8. POST /v1/requests ──────────────────────────────────────────────────────
RESP=$(curl -sf -X POST "http://localhost:$PORT/v1/requests" \
  -H "Content-Type: application/json" \
  -d '{"request_text":"smoke test ping","priority":"normal"}')
check "POST /v1/requests → 202 queued" "$RESP" '"status":"queued"'

REQUEST_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['request_id'])" 2>/dev/null || echo "")

# ── 9. GET /v1/requests/{id} ──────────────────────────────────────────────────
if [[ -n "$REQUEST_ID" ]]; then
  check "GET /v1/requests/$REQUEST_ID → has request_id" \
    "$(curl -sf http://localhost:$PORT/v1/requests/$REQUEST_ID)" '"request_id"'
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "[smoke] Results: $PASS passed, $FAIL failed"

if $KEEP; then
  echo "[smoke] Server still running — PID $SERVER_PID on :$PORT"
  echo "[smoke] Stop with: kill $SERVER_PID"
else
  kill $SERVER_PID 2>/dev/null
  echo "[smoke] Server stopped."
fi

[[ $FAIL -eq 0 ]]
