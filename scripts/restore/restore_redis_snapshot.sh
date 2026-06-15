#!/usr/bin/env bash
# restore_redis_snapshot.sh — restore an ElastiCache (Redis) replication group from a snapshot.
#
# Creates a NEW, throwaway Redis cluster seeded from a named snapshot. Never
# restores onto a production cluster; the target name is always distinct so the
# caller can tear it down after the drill.
#
# DRY-RUN BY DEFAULT: with no flags this prints the resolved restore plan and
# performs NO AWS mutations. Pass --execute to actually run the restore.
# Safe to run in CI in dry-run mode.
#
# Config (environment variables):
#   AWS_REGION            AWS region                              (default: us-east-1)
#   REDIS_SNAPSHOT_NAME   source snapshot name                    (required)
#   REDIS_TARGET_GROUP_ID target (throwaway) replication group id (default: redis-restore-drill)
#   REDIS_NODE_TYPE       cache node type for the target          (default: cache.t4g.small)
#   REDIS_SUBNET_GROUP    cache subnet group for the target       (optional)
#
# Spec: docs/resilience/backup-restore-policy.md · ADR-0082
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Usage: ${SCRIPT_NAME} [--dry-run | --execute] [-h|--help]

Restore an ElastiCache (Redis) replication group from a snapshot, into a throwaway target.

Options:
  --dry-run   Print the restore plan and exit without mutating anything (default).
  --execute   Actually perform the snapshot restore (requires AWS credentials).
  -h, --help  Show this help and exit.

Environment:
  AWS_REGION            (default: us-east-1)
  REDIS_SNAPSHOT_NAME   source snapshot name                     (required)
  REDIS_TARGET_GROUP_ID target throwaway replication group id    (default: redis-restore-drill)
  REDIS_NODE_TYPE       cache node type for the target           (default: cache.t4g.small)
  REDIS_SUBNET_GROUP    cache subnet group for the target        (optional)
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
SNAPSHOT_NAME="${REDIS_SNAPSHOT_NAME:-}"
if [ -z "${SNAPSHOT_NAME}" ]; then
  echo "ERROR: REDIS_SNAPSHOT_NAME is required" >&2
  exit 2
fi
TARGET_GROUP_ID="${REDIS_TARGET_GROUP_ID:-redis-restore-drill}"
NODE_TYPE="${REDIS_NODE_TYPE:-cache.t4g.small}"
SUBNET_GROUP="${REDIS_SUBNET_GROUP:-}"

echo "== Redis snapshot restore plan =="
echo "  region:        ${AWS_REGION}"
echo "  snapshot:      ${SNAPSHOT_NAME}"
echo "  target group:  ${TARGET_GROUP_ID} (throwaway)"
echo "  node type:     ${NODE_TYPE}"
echo "  subnet group:  ${SUBNET_GROUP:-<account default>}"
echo "  mode:          ${MODE}"

build_args() {
  set -- \
    --replication-group-id "${TARGET_GROUP_ID}" \
    --replication-group-description "restore-drill from ${SNAPSHOT_NAME}" \
    --snapshot-name "${SNAPSHOT_NAME}" \
    --cache-node-type "${NODE_TYPE}"
  if [ -n "${SUBNET_GROUP}" ]; then
    set -- "$@" --cache-subnet-group-name "${SUBNET_GROUP}"
  fi
  printf '%s\n' "$@"
}

if [ "${MODE}" = "dry-run" ]; then
  echo "-- DRY RUN: would invoke aws elasticache create-replication-group with:"
  build_args | sed 's/^/     /'
  echo "-- No AWS mutations performed."
  exit 0
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found; cannot --execute" >&2
  exit 1
fi

echo "-- EXECUTE: restoring Redis replication group from snapshot..."
mapfile -t EC_ARGS < <(build_args)
aws elasticache create-replication-group \
  --region "${AWS_REGION}" \
  "${EC_ARGS[@]}"
echo "-- Restore initiated for target replication group ${TARGET_GROUP_ID}."
