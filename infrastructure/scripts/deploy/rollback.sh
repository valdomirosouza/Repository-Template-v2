#!/usr/bin/env bash
set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
ENV=""
SERVICE="app"
REVISION=""
NAMESPACE=""
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus:9090}"
MONITOR_WINDOW_SECONDS=600  # 10 min post-rollback monitoring

# ── Argument parsing ──────────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 --env <staging|production> [--service <name>] [--revision <n>]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --env)      ENV="$2";      shift 2 ;;
    --service)  SERVICE="$2";  shift 2 ;;
    --revision) REVISION="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ -z "$ENV" ]] && usage
NAMESPACE="${ENV}"

log() { echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"level\":\"$1\",\"msg\":\"$2\",\"env\":\"$ENV\",\"service\":\"$SERVICE\"}"; }

# ── Get previous stable revision ──────────────────────────────────────────────
get_previous_revision() {
  if [[ -n "$REVISION" ]]; then
    echo "$REVISION"
    return
  fi
  helm history "$SERVICE" --namespace "$NAMESPACE" --output json \
    | jq -r '[.[] | select(.status == "deployed" or .status == "superseded")] | sort_by(.revision) | .[-2].revision // empty'
}

# ── Execute rollback ──────────────────────────────────────────────────────────
execute_rollback() {
  local rev="$1"
  if [[ -z "$rev" ]]; then
    log ERROR "No previous revision found for rollback"
    exit 1
  fi

  log INFO "Rolling back ${SERVICE} in ${NAMESPACE} to revision ${rev}"
  helm rollback "$SERVICE" "$rev" \
    --namespace "$NAMESPACE" \
    --wait \
    --timeout 5m

  log INFO "Rollback to revision ${rev} complete"
}

# ── Post-rollback smoke test ──────────────────────────────────────────────────
post_rollback_smoke_test() {
  log INFO "Running post-rollback smoke tests"
  BASE_URL="${BASE_URL:-http://${SERVICE}.${NAMESPACE}.svc.cluster.local}"
  if bash "$(dirname "$0")/smoke-test.sh" --env "$ENV" --base-url "$BASE_URL"; then
    log INFO "Post-rollback smoke tests passed"
  else
    log ERROR "Post-rollback smoke tests FAILED — service may still be degraded"
    exit 2
  fi
}

# ── Golden Signals monitoring window ─────────────────────────────────────────
monitor_post_rollback() {
  log INFO "Monitoring Golden Signals for ${MONITOR_WINDOW_SECONDS}s after rollback"
  sleep "$MONITOR_WINDOW_SECONDS"

  ERROR_RATE=$(curl -sf "${PROMETHEUS_URL}/api/v1/query" \
    --data-urlencode "query=sum(rate(http_requests_total{status=~\"5..\",namespace=\"${NAMESPACE}\"}[5m])) / sum(rate(http_requests_total{namespace=\"${NAMESPACE}\"}[5m]))" \
    | jq -r '.data.result[0].value[1] // "0"')

  P99=$(curl -sf "${PROMETHEUS_URL}/api/v1/query" \
    --data-urlencode "query=histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{namespace=\"${NAMESPACE}\"}[5m])) by (le))" \
    | jq -r '.data.result[0].value[1] // "0"')

  log INFO "Post-rollback Golden Signals: error_rate=${ERROR_RATE} p99=${P99}s"

  if (( $(echo "$ERROR_RATE > 0.01" | bc -l) )) || (( $(echo "$P99 > 0.5" | bc -l) )); then
    log ERROR "Golden Signals still degraded after rollback — escalate to on-call"
    notify_monitoring "ROLLBACK_DEGRADED" "error_rate=${ERROR_RATE} p99=${P99}s"
    exit 1
  fi

  log INFO "Service recovered after rollback — Golden Signals within SLO"
  notify_monitoring "ROLLBACK_SUCCESS" "error_rate=${ERROR_RATE} p99=${P99}s"
}

# ── Notification ──────────────────────────────────────────────────────────────
notify_monitoring() {
  local status="$1"
  local detail="$2"
  log INFO "Notification: status=${status} detail=${detail}"
  # Replace with actual webhook/alerting integration
  curl -sf "${MONITORING_WEBHOOK_URL:-http://localhost/noop}" \
    -H "Content-Type: application/json" \
    -d "{\"event\":\"rollback\",\"status\":\"${status}\",\"env\":\"${ENV}\",\"service\":\"${SERVICE}\",\"detail\":\"${detail}\"}" \
    2>/dev/null || true
}

# ── Main ──────────────────────────────────────────────────────────────────────
log INFO "Rollback initiated for ${SERVICE} in ${NAMESPACE}"

PREV_REV=$(get_previous_revision)
log INFO "Target revision: ${PREV_REV:-auto-detect}"

execute_rollback "$PREV_REV"
post_rollback_smoke_test
monitor_post_rollback

log INFO "Rollback complete and service verified healthy"
exit 0
