#!/usr/bin/env bash
set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
STRATEGY="canary"
ENV=""
VERSION=""
SERVICE="app"
NAMESPACE=""
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus:9090}"
HELM_TIMEOUT="5m"
CANARY_WAIT_SECONDS=900  # 15 min per weight step
ERROR_RATE_THRESHOLD="0.01"
P99_THRESHOLD_SECONDS="0.5"

# ── Argument parsing ──────────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 --strategy <canary|blue-green|rolling> --env <staging|production> --version <semver> [--service <name>]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --strategy) STRATEGY="$2"; shift 2 ;;
    --env)      ENV="$2";      shift 2 ;;
    --version)  VERSION="$2";  shift 2 ;;
    --service)  SERVICE="$2";  shift 2 ;;
    *) usage ;;
  esac
done

[[ -z "$ENV" || -z "$VERSION" ]] && usage
NAMESPACE="${ENV}"

log() { echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"level\":\"$1\",\"msg\":\"$2\",\"env\":\"$ENV\",\"version\":\"$VERSION\",\"strategy\":\"$STRATEGY\"}"; }

# ── Auto-rollback trap ────────────────────────────────────────────────────────
trap 'log ERROR "Deploy failed — triggering auto-rollback"; bash "$(dirname "$0")/rollback.sh" --env "$ENV" --service "$SERVICE"; exit 1' ERR

# ── Pre-deploy health check ───────────────────────────────────────────────────
pre_deploy_check() {
  log INFO "Running pre-deploy health check"
  READY=$(kubectl get deployment "$SERVICE" -n "$NAMESPACE" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
  DESIRED=$(kubectl get deployment "$SERVICE" -n "$NAMESPACE" \
    -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
  if [[ "$READY" -lt "$DESIRED" ]]; then
    log ERROR "Pre-deploy check failed: $READY/$DESIRED pods ready before deploy started"
    exit 1
  fi
  log INFO "Pre-deploy check passed: $READY/$DESIRED pods ready"
}

# ── Golden Signals check ──────────────────────────────────────────────────────
check_golden_signals() {
  local label="${1:-post-deploy}"
  log INFO "Checking Golden Signals ($label)"

  ERROR_RATE=$(curl -sf "${PROMETHEUS_URL}/api/v1/query" \
    --data-urlencode "query=sum(rate(http_requests_total{status=~\"5..\",namespace=\"${NAMESPACE}\"}[5m])) / sum(rate(http_requests_total{namespace=\"${NAMESPACE}\"}[5m]))" \
    | jq -r '.data.result[0].value[1] // "0"')

  P99=$(curl -sf "${PROMETHEUS_URL}/api/v1/query" \
    --data-urlencode "query=histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{namespace=\"${NAMESPACE}\"}[5m])) by (le))" \
    | jq -r '.data.result[0].value[1] // "0"')

  log INFO "Golden Signals: error_rate=${ERROR_RATE} p99=${P99}s"

  if (( $(echo "$ERROR_RATE > $ERROR_RATE_THRESHOLD" | bc -l) )); then
    log ERROR "Golden Signals gate FAILED: error_rate=${ERROR_RATE} > threshold=${ERROR_RATE_THRESHOLD}"
    return 1
  fi
  if (( $(echo "$P99 > $P99_THRESHOLD_SECONDS" | bc -l) )); then
    log ERROR "Golden Signals gate FAILED: p99=${P99}s > threshold=${P99_THRESHOLD_SECONDS}s"
    return 1
  fi

  log INFO "Golden Signals gate PASSED"
}

# ── Smoke tests ───────────────────────────────────────────────────────────────
run_smoke_tests() {
  log INFO "Running smoke tests"
  BASE_URL="${BASE_URL:-http://${SERVICE}.${NAMESPACE}.svc.cluster.local}"
  bash "$(dirname "$0")/smoke-test.sh" --env "$ENV" --base-url "$BASE_URL"
  log INFO "Smoke tests passed"
}

# ── Canary deploy ─────────────────────────────────────────────────────────────
deploy_canary() {
  log INFO "Starting canary deploy: 5% → 25% → 100%"

  for WEIGHT in 5 25 100; do
    log INFO "Promoting canary to ${WEIGHT}%"
    helm upgrade --install "$SERVICE" ./infrastructure/helm/ \
      --namespace "$NAMESPACE" \
      --set "image.tag=${VERSION}" \
      --set "canary.enabled=$([ "$WEIGHT" -lt 100 ] && echo true || echo false)" \
      --set "canary.weight=${WEIGHT}" \
      --wait --timeout "$HELM_TIMEOUT"

    if [[ "$WEIGHT" -lt 100 ]]; then
      log INFO "Waiting ${CANARY_WAIT_SECONDS}s to observe metrics at ${WEIGHT}%"
      sleep "$CANARY_WAIT_SECONDS"
      check_golden_signals "canary-${WEIGHT}pct"
    fi
  done

  run_smoke_tests
  log INFO "Canary deploy complete: 100% traffic on version ${VERSION}"
}

# ── Blue-green deploy ─────────────────────────────────────────────────────────
deploy_blue_green() {
  log INFO "Starting blue-green deploy"
  ACTIVE=$(kubectl get service "$SERVICE" -n "$NAMESPACE" \
    -o jsonpath='{.spec.selector.slot}' 2>/dev/null || echo "blue")
  INACTIVE=$([ "$ACTIVE" = "blue" ] && echo "green" || echo "blue")

  log INFO "Active slot: ${ACTIVE} | Deploying to inactive slot: ${INACTIVE}"
  helm upgrade --install "${SERVICE}-${INACTIVE}" ./infrastructure/helm/ \
    --namespace "$NAMESPACE" \
    --set "image.tag=${VERSION}" \
    --set "slot=${INACTIVE}" \
    --wait --timeout "$HELM_TIMEOUT"

  run_smoke_tests

  log INFO "Switching traffic from ${ACTIVE} to ${INACTIVE}"
  kubectl patch service "$SERVICE" -n "$NAMESPACE" \
    -p "{\"spec\":{\"selector\":{\"slot\":\"${INACTIVE}\"}}}"

  check_golden_signals "blue-green-switchover"
  log INFO "Blue-green deploy complete. Old slot ${ACTIVE} retained for 30-min rollback window."
}

# ── Rolling deploy ────────────────────────────────────────────────────────────
deploy_rolling() {
  log INFO "Starting rolling deploy (maxUnavailable=0)"
  helm upgrade --install "$SERVICE" ./infrastructure/helm/ \
    --namespace "$NAMESPACE" \
    --set "image.tag=${VERSION}" \
    --set "rollingUpdate.maxUnavailable=0" \
    --set "rollingUpdate.maxSurge=1" \
    --wait --timeout "$HELM_TIMEOUT"

  run_smoke_tests
  check_golden_signals "post-rolling"
  log INFO "Rolling deploy complete"
}

# ── Main ──────────────────────────────────────────────────────────────────────
pre_deploy_check

case "$STRATEGY" in
  canary)     deploy_canary ;;
  blue-green) deploy_blue_green ;;
  rolling)    deploy_rolling ;;
  *) log ERROR "Unknown strategy: $STRATEGY"; exit 1 ;;
esac

log INFO "Deploy finished successfully"
exit 0
