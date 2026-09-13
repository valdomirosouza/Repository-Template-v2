#!/usr/bin/env bash
# template_sync.sh — three-way template sync for adopters (W14-T1, issue #376, ADR-0087).
#
# Replaces `git checkout template/main -- .` (which overwrote every adopter edit outside a fixed
# nine-path list) with a per-path three-way merge against the template commit the adopter is
# actually on, recorded in `.template-version`. Paths the adopter owns are listed in
# `.template-sync.yml` (`exclude:`), not hard-coded in the workflow.
#
# Usage:
#   scripts/template_sync.sh --template-url <url> [--template-ref main] [--dry-run]
#
# Outcome per path:
#   unchanged     template did not change the file since the recorded base — nothing to do
#   fast-forward  adopter did not touch it — take the template version
#   merged        both changed, merged cleanly (git merge-file)
#   CONFLICT      both changed the same hunk — conflict markers left for the reviewer
#   excluded      listed in .template-sync.yml — never touched
#   added         new in the template — added
#   deleted       removed by the template and untouched by the adopter — removed
#
# Exit 0 always (the reviewer decides); prints a summary and writes .template-version.
set -euo pipefail

TEMPLATE_URL=""; TEMPLATE_REF="main"; DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --template-url) TEMPLATE_URL="$2"; shift 2 ;;
    --template-ref) TEMPLATE_REF="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown arg $1" >&2; exit 64 ;;
  esac
done
[ -n "$TEMPLATE_URL" ] || { echo "--template-url is required" >&2; exit 64; }

ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
VERSION_FILE=".template-version"
CONFIG_FILE=".template-sync.yml"

git remote get-url template >/dev/null 2>&1 || git remote add template "$TEMPLATE_URL"
git fetch --quiet template "$TEMPLATE_REF"
NEW_BASE="$(git rev-parse "template/$TEMPLATE_REF")"

# Base = recorded template commit; first sync falls back to the merge-base (or the new tip
# itself, which degrades to "take template for untouched files, keep adopter edits").
if [ -f "$VERSION_FILE" ] && git cat-file -e "$(cut -d' ' -f1 "$VERSION_FILE")^{commit}" 2>/dev/null; then
  OLD_BASE="$(cut -d' ' -f1 "$VERSION_FILE")"
else
  OLD_BASE="$(git merge-base HEAD "$NEW_BASE" 2>/dev/null || echo "$NEW_BASE")"
fi

# Excludes: .template-sync.yml `exclude:` list (one path per `- ` line); defaults if absent.
EXCLUDES=()
if [ -f "$CONFIG_FILE" ]; then
  while IFS= read -r line; do [ -n "$line" ] && EXCLUDES+=("$line"); done < <(awk '/^exclude:/{f=1;next} f&&/^[^ -]/{f=0} f&&/^ *- /{sub(/^ *- */,""); gsub(/["'"'"']/,""); print}' "$CONFIG_FILE")
else
  EXCLUDES=(CLAUDE.md CLAUDE_SESSION_INIT.md services.yaml .env.example docs/adr specs CHANGELOG.md .github/CODEOWNERS AGENTS.md)
fi
is_excluded() { local p="$1" e; for e in "${EXCLUDES[@]:-}"; do [ -n "$e" ] || continue; case "$p" in "$e"|"$e"/*) return 0 ;; esac; done; return 1; }

# Counters (plain variables: macOS ships bash 3.2, no associative arrays)
N_unchanged=0; N_fastforward=0; N_merged=0; N_CONFLICT=0; N_excluded=0; N_added=0; N_deleted=0
note() {
  case "$1" in
    unchanged) N_unchanged=$((N_unchanged+1)) ;; fast-forward) N_fastforward=$((N_fastforward+1)) ;;
    merged) N_merged=$((N_merged+1)) ;; CONFLICT) N_CONFLICT=$((N_CONFLICT+1)) ;;
    excluded) N_excluded=$((N_excluded+1)) ;; added) N_added=$((N_added+1)) ;; deleted) N_deleted=$((N_deleted+1)) ;;
  esac
  printf '%-13s %s\n' "$1" "$2"
}

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
while IFS=$'\t' read -r status path; do
  [ -n "$path" ] || continue
  if is_excluded "$path"; then note excluded "$path"; continue; fi
  case "$status" in
    A)
      if [ -e "$path" ]; then
        # adopter created the same path independently → treat as both-changed against empty base
        : > "$TMP/base"; git show "$NEW_BASE:$path" > "$TMP/theirs"
        if git merge-file -p "$path" "$TMP/base" "$TMP/theirs" > "$TMP/out"; then
          [ "$DRY_RUN" = 1 ] || cp "$TMP/out" "$path"; note merged "$path"
        else
          [ "$DRY_RUN" = 1 ] || cp "$TMP/out" "$path"; note CONFLICT "$path"
        fi
      else
        [ "$DRY_RUN" = 1 ] || { mkdir -p "$(dirname "$path")"; git show "$NEW_BASE:$path" > "$path"; }
        note added "$path"
      fi ;;
    D)
      if [ -e "$path" ] && git diff --quiet "$OLD_BASE" -- "$path" 2>/dev/null; then
        [ "$DRY_RUN" = 1 ] || git rm -q -- "$path"; note deleted "$path"
      else
        note unchanged "$path (template deleted; adopter modified — kept)"
      fi ;;
    M|R*|T)
      if [ ! -e "$path" ]; then note unchanged "$path (adopter removed it — kept removed)"; continue; fi
      git show "$OLD_BASE:$path" > "$TMP/base" 2>/dev/null || : > "$TMP/base"
      git show "$NEW_BASE:$path" > "$TMP/theirs"
      if cmp -s "$path" "$TMP/base"; then
        [ "$DRY_RUN" = 1 ] || cp "$TMP/theirs" "$path"; note fast-forward "$path"
      elif git merge-file -p "$path" "$TMP/base" "$TMP/theirs" > "$TMP/out"; then
        [ "$DRY_RUN" = 1 ] || cp "$TMP/out" "$path"; note merged "$path"
      else
        [ "$DRY_RUN" = 1 ] || cp "$TMP/out" "$path"; note CONFLICT "$path"
      fi ;;
  esac
done < <(git diff --name-status "$OLD_BASE" "$NEW_BASE")

[ "$DRY_RUN" = 1 ] || printf '%s %s\n' "$NEW_BASE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$VERSION_FILE"
echo
echo "template sync: base ${OLD_BASE:0:12} → ${NEW_BASE:0:12}"
printf '  %-13s %s\n' fast-forward "$N_fastforward" merged "$N_merged" added "$N_added" deleted "$N_deleted" CONFLICT "$N_CONFLICT" excluded "$N_excluded" unchanged "$N_unchanged"
[ "$N_CONFLICT" = 0 ] || echo "  review the CONFLICT files above before merging the sync PR"
