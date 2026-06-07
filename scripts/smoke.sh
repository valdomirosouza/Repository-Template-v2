#!/usr/bin/env bash
# smoke.sh — post-setup confidence check for the active adoption profile.
#
# Reads PROFILE from .env (default: core) and runs the checks relevant to that profile:
# API health/ready, fast unit tests, lint, and — for core+ — PostgreSQL/Redis
# reachability, and for full — Kafka. Prints a summary table and exits 0 only if every
# check relevant to the profile passes.
#
# Reusability Uplift v2.0.0 (ADR-0059). Spec: reusability-uplift-v2.0.0.md Improvement 7.
set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1

if [ -t 1 ]; then
  GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; RESET=$'\033[0m'
else
  GREEN=""; RED=""; RESET=""
fi

PROFILE="core"
if [ -f .env ] && grep -qE '^PROFILE=' .env; then
  PROFILE="$(grep -E '^PROFILE=' .env | head -1 | cut -d= -f2-)"
fi

API_PORT="${APP_PORT:-8000}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
KAFKA_PORT="${KAFKA_PORT:-9092}"

# results: "NAME|PASS|detail" lines
results=()
overall=0

record() { results+=("$1|$2|$3"); [ "$2" = "FAIL" ] && overall=1; return 0; }

http_json() {
  # http_json URL EXPECT_SUBSTRING NAME
  local url="$1" expect="$2" name="$3" body
  if ! command -v curl >/dev/null 2>&1; then record "$name" "FAIL" "curl not installed"; return; fi
  body="$(curl -fsS --max-time 5 "$url" 2>/dev/null || true)"
  if printf '%s' "$body" | grep -q "$expect"; then record "$name" "PASS" "$url"
  else record "$name" "FAIL" "$url did not return '$expect' (got: ${body:-no response})"; fi
}

run_make() {
  # run_make TARGET NAME
  if make "$1" >/tmp/smoke-"$1".log 2>&1; then record "$2" "PASS" "make $1"
  else record "$2" "FAIL" "make $1 (see /tmp/smoke-$1.log)"; fi
}

# ── Always: API health/ready, unit tests, lint ─────────────────────────────────
http_json "http://localhost:${API_PORT}/health" '"status"' "API /health"
http_json "http://localhost:${API_PORT}/ready"  'ready'    "API /ready"
run_make test-unit-python "Unit tests"
run_make lint-python      "Lint"

# ── core and higher: PostgreSQL + Redis ────────────────────────────────────────
if [ "$PROFILE" != "minimal" ]; then
  if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h localhost -p "$POSTGRES_PORT" >/dev/null 2>&1; then record "PostgreSQL" "PASS" "pg_isready :$POSTGRES_PORT"
    else record "PostgreSQL" "FAIL" "pg_isready :$POSTGRES_PORT not ready"; fi
  else
    record "PostgreSQL" "PASS" "pg_isready not installed — skipped"
  fi
  if command -v redis-cli >/dev/null 2>&1; then
    if [ "$(redis-cli -p "$REDIS_PORT" ping 2>/dev/null || true)" = "PONG" ]; then record "Redis" "PASS" "redis-cli ping"
    else record "Redis" "FAIL" "redis-cli ping did not return PONG"; fi
  else
    record "Redis" "PASS" "redis-cli not installed — skipped"
  fi
fi

# ── full: Kafka ────────────────────────────────────────────────────────────────
if [ "$PROFILE" = "full" ]; then
  if command -v kafka-topics.sh >/dev/null 2>&1; then
    if kafka-topics.sh --bootstrap-server "localhost:$KAFKA_PORT" --list >/dev/null 2>&1; then record "Kafka" "PASS" "topics --list"
    else record "Kafka" "FAIL" "kafka-topics --list failed"; fi
  else
    record "Kafka" "PASS" "kafka CLI not installed — skipped"
  fi
fi

# ── Summary table ──────────────────────────────────────────────────────────────
echo
echo "Smoke test — profile: $PROFILE"
printf '  %-16s %-6s %s\n' "CHECK" "RESULT" "DETAIL"
printf '  %-16s %-6s %s\n' "----------------" "------" "------"
for r in "${results[@]}"; do
  IFS='|' read -r name status detail <<< "$r"
  if [ "$status" = "PASS" ]; then colour="$GREEN"; else colour="$RED"; fi
  printf '  %-16s %s%-6s%s %s\n' "$name" "$colour" "$status" "$RESET" "$detail"
done
echo

if [ "$overall" -ne 0 ]; then
  echo "${RED}Smoke test failed for profile '$PROFILE'. Fix the FAIL items above.${RESET}"
  exit 1
fi
echo "${GREEN}Smoke test passed for profile '$PROFILE'.${RESET}"
