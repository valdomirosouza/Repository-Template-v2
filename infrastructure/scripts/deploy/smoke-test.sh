#!/usr/bin/env bash
set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
ENV=""
BASE_URL=""
TIMEOUT_SECONDS=10
MAX_RETRIES=3
RETRY_BACKOFF=5
RESULTS=()

# ── Argument parsing ──────────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 --env <staging|production> --base-url <url>"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --env)      ENV="$2";      shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ -z "$ENV" || -z "$BASE_URL" ]] && usage

log() { echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"level\":\"$1\",\"check\":\"$2\",\"result\":\"$3\",\"detail\":\"${4:-}\"}"; }

# ── HTTP check with retry ─────────────────────────────────────────────────────
http_check() {
  local name="$1"
  local url="$2"
  local expected_status="${3:-200}"
  local body_pattern="${4:-}"
  local attempt=0
  local start_ms

  while [[ $attempt -lt $MAX_RETRIES ]]; do
    attempt=$(( attempt + 1 ))
    start_ms=$(date +%s%3N)

    RESPONSE=$(curl -sf \
      --max-time "$TIMEOUT_SECONDS" \
      --write-out "\n%{http_code}" \
      "$url" 2>/dev/null || echo -e "\n000")

    BODY=$(echo "$RESPONSE" | head -n -1)
    STATUS=$(echo "$RESPONSE" | tail -n 1)
    DURATION=$(( $(date +%s%3N) - start_ms ))

    if [[ "$STATUS" == "$expected_status" ]]; then
      if [[ -n "$body_pattern" ]] && ! echo "$BODY" | grep -q "$body_pattern"; then
        log WARN "$name" "FAIL" "status=${STATUS} body_pattern_not_found=${body_pattern} attempt=${attempt} duration_ms=${DURATION}"
      else
        log INFO "$name" "PASS" "status=${STATUS} duration_ms=${DURATION}"
        RESULTS+=("{\"check\":\"${name}\",\"result\":\"PASS\",\"status\":${STATUS},\"duration_ms\":${DURATION}}")
        return 0
      fi
    else
      log WARN "$name" "FAIL" "status=${STATUS} expected=${expected_status} attempt=${attempt} duration_ms=${DURATION}"
    fi

    [[ $attempt -lt $MAX_RETRIES ]] && sleep "$RETRY_BACKOFF"
  done

  log ERROR "$name" "FAIL" "exhausted_retries=${MAX_RETRIES}"
  RESULTS+=("{\"check\":\"${name}\",\"result\":\"FAIL\",\"status\":${STATUS:-0},\"duration_ms\":${DURATION:-0}}")
  return 1
}

# ── Checks ────────────────────────────────────────────────────────────────────
check_health() {
  http_check "health" "${BASE_URL}/health" 200 '"status":"ok"'
}

check_readiness() {
  http_check "readiness" "${BASE_URL}/ready" 200
}

check_api_status() {
  http_check "api-status" "${BASE_URL}/v1/status" 200
}

check_hitl_connectivity() {
  http_check "hitl-gateway" "${BASE_URL}/v1/hitl/status" 200
}

check_metrics() {
  http_check "prometheus-metrics" "${BASE_URL}/metrics" 200 "http_requests_total"
}

# ── Summary output ────────────────────────────────────────────────────────────
print_summary() {
  local passed=0
  local failed=0
  for r in "${RESULTS[@]}"; do
    if echo "$r" | grep -q '"result":"PASS"'; then
      (( passed++ ))
    else
      (( failed++ ))
    fi
  done

  echo ""
  echo "{"
  echo "  \"env\": \"${ENV}\","
  echo "  \"base_url\": \"${BASE_URL}\","
  echo "  \"passed\": ${passed},"
  echo "  \"failed\": ${failed},"
  echo "  \"checks\": [$(IFS=,; echo "${RESULTS[*]}")]"
  echo "}"

  [[ $failed -eq 0 ]]
}

# ── Main ──────────────────────────────────────────────────────────────────────
log INFO "smoke-tests" "START" "env=${ENV} base_url=${BASE_URL}"

FAILED=0
check_health       || FAILED=1
check_readiness    || FAILED=1
check_api_status   || FAILED=1
check_hitl_connectivity || FAILED=1
check_metrics      || FAILED=1

print_summary

if [[ $FAILED -eq 1 ]]; then
  log ERROR "smoke-tests" "FAIL" "one or more checks failed"
  exit 1
fi

log INFO "smoke-tests" "PASS" "all checks passed"
exit 0
