#!/usr/bin/env bash
# restore_aurora_pitr.sh — restore an Aurora PostgreSQL cluster to a point in time.
#
# Restores the source Aurora cluster to a NEW, throwaway target cluster using
# point-in-time recovery (PITR). Never restores onto a production resource; the
# target is always a freshly-named cluster the caller can tear down afterwards.
#
# DRY-RUN BY DEFAULT: with no flags this prints the resolved restore plan and
# performs NO AWS mutations. Pass --execute to actually run the restore.
# Safe to run in CI in dry-run mode.
#
# Config (environment variables):
#   AWS_REGION                AWS region                          (default: us-east-1)
#   AURORA_SOURCE_CLUSTER_ID  source cluster identifier           (required)
#   AURORA_TARGET_CLUSTER_ID  target (throwaway) cluster id       (default: <source>-restore-drill)
#   AURORA_RESTORE_TO_TIME    restore point, ISO-8601 UTC         (default: latest restorable time)
#   AURORA_SUBNET_GROUP       DB subnet group for target          (optional)
#
# Spec: docs/resilience/backup-restore-policy.md · ADR-0082 · ADR-0062 (Aurora HA)
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Usage: ${SCRIPT_NAME} [--dry-run | --execute] [-h|--help]

Restore an Aurora PostgreSQL cluster to a point in time, into a throwaway target.

Options:
  --dry-run   Print the restore plan and exit without mutating anything (default).
  --execute   Actually perform the PITR restore (requires AWS credentials).
  -h, --help  Show this help and exit.

Environment:
  AWS_REGION                (default: us-east-1)
  AURORA_SOURCE_CLUSTER_ID  source cluster id                       (required)
  AURORA_TARGET_CLUSTER_ID  target throwaway cluster id             (default: <source>-restore-drill)
  AURORA_RESTORE_TO_TIME    ISO-8601 UTC restore point              (default: latest restorable time)
  AURORA_SUBNET_GROUP       DB subnet group for the target cluster  (optional)
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
SOURCE_ID="${AURORA_SOURCE_CLUSTER_ID:-}"
if [ -z "${SOURCE_ID}" ]; then
  echo "ERROR: AURORA_SOURCE_CLUSTER_ID is required" >&2
  exit 2
fi
TARGET_ID="${AURORA_TARGET_CLUSTER_ID:-${SOURCE_ID}-restore-drill}"
RESTORE_TO_TIME="${AURORA_RESTORE_TO_TIME:-}"
SUBNET_GROUP="${AURORA_SUBNET_GROUP:-}"

echo "== Aurora PITR restore plan =="
echo "  region:        ${AWS_REGION}"
echo "  source cluster: ${SOURCE_ID}"
echo "  target cluster: ${TARGET_ID} (throwaway)"
if [ -n "${RESTORE_TO_TIME}" ]; then
  echo "  restore-to:    ${RESTORE_TO_TIME}"
else
  echo "  restore-to:    latest restorable time"
fi
echo "  subnet group:  ${SUBNET_GROUP:-<account default>}"
echo "  mode:          ${MODE}"

build_args() {
  set -- \
    --source-db-cluster-identifier "${SOURCE_ID}" \
    --db-cluster-identifier "${TARGET_ID}"
  if [ -n "${RESTORE_TO_TIME}" ]; then
    set -- "$@" --restore-to-time "${RESTORE_TO_TIME}"
  else
    set -- "$@" --use-latest-restorable-time
  fi
  if [ -n "${SUBNET_GROUP}" ]; then
    set -- "$@" --db-subnet-group-name "${SUBNET_GROUP}"
  fi
  printf '%s\n' "$@"
}

if [ "${MODE}" = "dry-run" ]; then
  echo "-- DRY RUN: would invoke aws rds restore-db-cluster-to-point-in-time with:"
  build_args | sed 's/^/     /'
  echo "-- No AWS mutations performed."
  exit 0
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found; cannot --execute" >&2
  exit 1
fi

echo "-- EXECUTE: restoring Aurora cluster to point in time..."
mapfile -t RDS_ARGS < <(build_args)
aws rds restore-db-cluster-to-point-in-time \
  --region "${AWS_REGION}" \
  "${RDS_ARGS[@]}"
echo "-- Restore initiated for target cluster ${TARGET_ID}."
