#!/usr/bin/env bash
# apply_branch_protection.sh — apply the versioned branch-protection rulesets (ADR-0071).
#
#   HUMAN ADMIN ACTION. This needs repo-admin scope and changes access controls. An AI agent
#   MUST NOT run this (CLAUDE.md §14; ADR-0015 sibling class) — it prepares the JSON only.
#
# Usage:
#   scripts/governance/apply_branch_protection.sh            # apply .github/rulesets/*.json
#   scripts/governance/apply_branch_protection.sh --dry-run  # show what would change, no writes
#   REPO=owner/name scripts/governance/apply_branch_protection.sh   # override target repo
#
# It is idempotent: a ruleset whose `name` already exists is UPDATED (PUT); otherwise CREATED.
set -euo pipefail

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
RULESET_DIR="$(git rev-parse --show-toplevel)/.github/rulesets"

echo "Target repo : $REPO"
echo "Rulesets    : $RULESET_DIR/*.json"
echo "Mode        : $([ "$DRY_RUN" = 1 ] && echo 'DRY-RUN (no writes)' || echo 'APPLY')"
echo "----------------------------------------------------------------------"

# Map of existing ruleset name -> id (so we update in place rather than duplicating).
existing="$(gh api "repos/$REPO/rulesets" --jq '.[] | "\(.name)\t\(.id)"' 2>/dev/null || true)"

for f in "$RULESET_DIR"/*.json; do
  name="$(jq -r '.name' "$f")"
  id="$(printf '%s\n' "$existing" | awk -F'\t' -v n="$name" '$1==n{print $2; exit}')"

  if [ -n "$id" ]; then
    echo "UPDATE  ruleset '$name' (id=$id)  <- $(basename "$f")"
    [ "$DRY_RUN" = 1 ] || gh api "repos/$REPO/rulesets/$id" -X PUT --input "$f" >/dev/null
  else
    echo "CREATE  ruleset '$name'  <- $(basename "$f")"
    [ "$DRY_RUN" = 1 ] || gh api "repos/$REPO/rulesets" -X POST --input "$f" >/dev/null
  fi
done

echo "----------------------------------------------------------------------"
if [ "$DRY_RUN" = 1 ]; then
  echo "DRY-RUN complete — no changes made. Re-run without --dry-run to apply."
else
  echo "Applied. Verify with: gh api repos/$REPO/rulesets --jq '.[].name'"
  echo "The scheduled branch-protection-audit workflow will flag any later drift."
fi
