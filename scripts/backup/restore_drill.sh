#!/usr/bin/env bash
# restore_drill.sh — backup restore-drill automation SCAFFOLD (ADR-0082).
#
#   scripts/backup/restore_drill.sh [--store postgres|redis-session|redis-timeseries] [--execute]
#
# Proves that the latest backup of a stateful store actually restores, by:
#   1. spinning up a SCRATCH, throwaway store (never live/prod),
#   2. restoring the LATEST backup/snapshot into it,
#   3. verifying integrity (row counts / a known canary key / `alembic current`),
#   4. writing dated evidence under docs/resilience/restore-drills/YYYY-MM-DD.md.
#
# ┌──────────────────────────────────────────────────────────────────────────────┐
# │ SAFETY: This is an INERT SCAFFOLD. It is --dry-run by DEFAULT and makes NO     │
# │ infrastructure calls. Every action below is printed, not performed. It is a    │
# │ skeleton to be wired to real backups later (per-store restore pointers live in │
# │ docs/sre/backup-recovery.md and docs/resilience/backup-restore-policy.md).      │
# │ --execute is intentionally NOT implemented: it refuses and exits non-zero so    │
# │ no one can accidentally run a real, destructive restore through this stub.       │
# │ Runbook: docs/sre/runbooks/RB-SRE-006-restore-drill.md                          │
# └──────────────────────────────────────────────────────────────────────────────┘
set -euo pipefail

DRY_RUN=true
STORE="postgres"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --store) STORE="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --execute) DRY_RUN=false; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$STORE" in
  postgres|redis-session|redis-timeseries) ;;
  *) echo "ERROR: --store must be postgres|redis-session|redis-timeseries (got: $STORE)" >&2; exit 2 ;;
esac

# The scaffold is not yet wired to real backups. Refuse any real execution so this
# stub can never perform a destructive restore. Remove this guard only when the
# per-store restore calls below are implemented and reviewed (ADR-0082).
if [ "$DRY_RUN" != "true" ]; then
  echo "REFUSING: --execute is not implemented — this is an inert scaffold (ADR-0082)." >&2
  echo "          Wire the real restore steps and remove this guard before enabling execution." >&2
  exit 3
fi

say() { echo "[dry-run] $*"; }

DRILL_DATE="$(date -u +%Y-%m-%d)"
EVIDENCE_FILE="docs/resilience/restore-drills/${DRILL_DATE}.md"

echo "=== Backup restore drill (DRY-RUN — no infrastructure calls) ==="
echo "store=${STORE}  date=${DRILL_DATE}"
echo

say "STEP 1 — Provision a SCRATCH, throwaway target (never live/prod)."
case "$STORE" in
  postgres)
    say "  would restore the latest Aurora snapshot/PITR target to a NEW cluster identifier"
    say "  (console/IaC) — see docs/resilience/backup-restore-policy.md 'point-in-time restore'." ;;
  redis-session|redis-timeseries)
    say "  would restore the latest ElastiCache daily snapshot to a NEW node" ;;
esac

say "STEP 2 — Restore the LATEST backup into the scratch target; start the RTO timer."

say "STEP 3 — Verify integrity against the SCRATCH endpoint:"
case "$STORE" in
  postgres)
    say "  - row counts within expected bounds"
    say "  - canary record present"
    say "  - 'uv run alembic current' matches the expected migration head" ;;
  redis-session|redis-timeseries)
    say "  - key count within expected bounds"
    say "  - canary key present (redis-cli EXISTS <canary-key>)" ;;
esac

say "STEP 4 — Record evidence (counts/hashes only — NEVER raw rows/PII):"
say "  would write ${EVIDENCE_FILE} from the template in"
say "  docs/resilience/restore-drills/README.md (store, backup id+age, scratch target,"
say "  integrity result, RTO achieved vs documented RTO, PASS/FAIL, owner)."

say "STEP 5 — Tear down the scratch target. On FAIL: open an 'incident' issue and page SRE."

echo
echo "Dry-run complete. No infrastructure was touched, no evidence file was written."
echo "To perform a real drill today, follow RB-SRE-006-restore-drill.md manually until this"
echo "scaffold is wired to real backups."
