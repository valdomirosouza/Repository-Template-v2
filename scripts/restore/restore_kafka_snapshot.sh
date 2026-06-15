#!/usr/bin/env bash
# restore_kafka_snapshot.sh — restore an Amazon MSK (Kafka) cluster from a snapshot.
#
# Creates a NEW, throwaway MSK cluster from a stored configuration/snapshot ARN.
# Never restores onto a production cluster; the target name is always distinct so
# the caller can tear it down after the drill.
#
# DRY-RUN BY DEFAULT: with no flags this prints the resolved restore plan and
# performs NO AWS mutations. Pass --execute to actually run the restore.
# Safe to run in CI in dry-run mode.
#
# Config (environment variables):
#   AWS_REGION              AWS region                            (default: us-east-1)
#   KAFKA_SNAPSHOT_ARN      source snapshot/backup ARN            (required)
#   KAFKA_TARGET_CLUSTER    target (throwaway) cluster name       (default: kafka-restore-drill)
#   KAFKA_KAFKA_VERSION     Kafka version for the target          (default: 3.6.0)
#   KAFKA_BROKER_COUNT      number of broker nodes                (default: 3)
#   KAFKA_INSTANCE_TYPE     broker instance type                  (default: kafka.m5.large)
#
# Spec: docs/resilience/backup-restore-policy.md · ADR-0082
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Usage: ${SCRIPT_NAME} [--dry-run | --execute] [-h|--help]

Restore an Amazon MSK (Kafka) cluster from a snapshot, into a throwaway target.

Options:
  --dry-run   Print the restore plan and exit without mutating anything (default).
  --execute   Actually perform the snapshot restore (requires AWS credentials).
  -h, --help  Show this help and exit.

Environment:
  AWS_REGION          (default: us-east-1)
  KAFKA_SNAPSHOT_ARN  source snapshot/backup ARN                 (required)
  KAFKA_TARGET_CLUSTER target throwaway cluster name             (default: kafka-restore-drill)
  KAFKA_KAFKA_VERSION Kafka version for the target               (default: 3.6.0)
  KAFKA_BROKER_COUNT  number of broker nodes                     (default: 3)
  KAFKA_INSTANCE_TYPE broker instance type                       (default: kafka.m5.large)
EOF
}

MODE="dry-run"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) MODE="dry-run" ;;
    --execute) MODE="execute" ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

AWS_REGION="${AWS_REGION:-us-east-1}"
SNAPSHOT_ARN="${KAFKA_SNAPSHOT_ARN:-}"
if [ -z "${SNAPSHOT_ARN}" ]; then
  echo "ERROR: KAFKA_SNAPSHOT_ARN is required" >&2
  exit 2
fi
TARGET_CLUSTER="${KAFKA_TARGET_CLUSTER:-kafka-restore-drill}"
KAFKA_VERSION="${KAFKA_KAFKA_VERSION:-3.6.0}"
BROKER_COUNT="${KAFKA_BROKER_COUNT:-3}"
INSTANCE_TYPE="${KAFKA_INSTANCE_TYPE:-kafka.m5.large}"

echo "== Kafka (MSK) snapshot restore plan =="
echo "  region:        ${AWS_REGION}"
echo "  snapshot ARN:  ${SNAPSHOT_ARN}"
echo "  target cluster: ${TARGET_CLUSTER} (throwaway)"
echo "  kafka version: ${KAFKA_VERSION}"
echo "  broker count:  ${BROKER_COUNT}"
echo "  instance type: ${INSTANCE_TYPE}"
echo "  mode:          ${MODE}"

build_args() {
  set -- \
    --cluster-name "${TARGET_CLUSTER}" \
    --kafka-version "${KAFKA_VERSION}" \
    --number-of-broker-nodes "${BROKER_COUNT}" \
    --source-snapshot-arn "${SNAPSHOT_ARN}" \
    --broker-node-group-info "InstanceType=${INSTANCE_TYPE}"
  printf '%s\n' "$@"
}

if [ "${MODE}" = "dry-run" ]; then
  echo "-- DRY RUN: would invoke aws kafka create-cluster (restore from snapshot) with:"
  build_args | sed 's/^/     /'
  echo "-- No AWS mutations performed."
  exit 0
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found; cannot --execute" >&2
  exit 1
fi

echo "-- EXECUTE: restoring MSK cluster from snapshot..."
mapfile -t MSK_ARGS < <(build_args)
aws kafka create-cluster \
  --region "${AWS_REGION}" \
  "${MSK_ARGS[@]}"
echo "-- Restore initiated for target cluster ${TARGET_CLUSTER}."
