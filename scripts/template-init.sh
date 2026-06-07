#!/usr/bin/env bash
# template-init.sh — first-run project initialisation for Repository-Template-v2.
#
# Replaces every template placeholder with your project's values, applies a per-language
# profile (removing service dirs you don't need), prepares .env, resets the version and
# changelog, and prints a summary with the remaining manual steps. Idempotent: running it
# again on an initialised repo is a no-op and still exits 0.
#
#   scripts/template-init.sh PROJECT_NAME ORG REGISTRY [PROFILE] [PACKAGE_ROOT]
#     PROFILE      = python-api | java-service | go-worker | frontend | full  (default full)
#     PACKAGE_ROOT = com.myorg  (Java only, optional)
#
# Reusability Uplift v2.0.0 (ADR-0059). Spec: reusability-uplift-v2.0.0.md Improvement 5.
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1

PROJECT_NAME="${1:-}"
ORG="${2:-}"
REGISTRY="${3:-}"
PROFILE="${4:-full}"
PACKAGE_ROOT="${5:-}"

if [ -z "$PROJECT_NAME" ] || [ -z "$ORG" ] || [ -z "$REGISTRY" ]; then
  echo "Usage: template-init.sh PROJECT_NAME ORG REGISTRY [PROFILE] [PACKAGE_ROOT]" >&2
  exit 1
fi
case "$PROFILE" in
  python-api|java-service|go-worker|frontend|full) ;;
  *) echo "ERROR: invalid PROFILE '$PROFILE' (python-api|java-service|go-worker|frontend|full)" >&2; exit 1 ;;
esac
PACKAGE_ROOT="${PACKAGE_ROOT:-com.$ORG}"

SELF="scripts/template-init.sh"

# replace_all FROM TO — fixed-string replace across tracked text files (skips this script).
replace_all() {
  local from="$1" to="$2" f
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    FROM="$from" TO="$to" perl -pi -e 's/\Q$ENV{FROM}\E/$ENV{TO}/g' "$f"
  done < <(git grep -I -l -F "$from" -- . ":!$SELF" 2>/dev/null || true)
}

echo "Initialising template → project '$PROJECT_NAME' (profile: $PROFILE)…"

# ── 1. Placeholder replacements ────────────────────────────────────────────────
replace_all "@your-org/"         "@$ORG/"
replace_all "github.com/yourorg" "github.com/$ORG"
replace_all "yourorg/"           "$REGISTRY/"
replace_all "com.yourorg"        "$PACKAGE_ROOT"
replace_all "template-service"   "$PROJECT_NAME"

# ── 2. Version reset → 0.1.0 (version.txt is the single source of truth, ADR-0057) ─
cur_version="$(cat version.txt 2>/dev/null || echo 0.0.0)"
echo "0.1.0" > version.txt
if [ -n "$cur_version" ]; then
  CUR="$cur_version" perl -pi -e 's/version = "\Q$ENV{CUR}\E"/version = "0.1.0"/' pyproject.toml
  CUR="$cur_version" perl -pi -e 's/\*\*Version:\*\* \Q$ENV{CUR}\E/**Version:** 0.1.0/' README.md
fi

# ── 3. Profile-based service removal ───────────────────────────────────────────
remove_dir() { [ -d "$1" ] && { rm -rf "$1"; echo "  removed $1"; } || true; }
case "$PROFILE" in
  python-api)   remove_dir services/domain-service; remove_dir services/event-worker; remove_dir frontend ;;
  java-service) remove_dir services/event-worker; remove_dir frontend ;;
  go-worker)    remove_dir services/domain-service; remove_dir frontend ;;
  frontend)     remove_dir services/domain-service; remove_dir services/event-worker ;;
  full)         : ;;  # keep everything
esac

# ── 4. .env preparation ────────────────────────────────────────────────────────
[ -f .env ] || cp .env.example .env
set_env() {
  local key="$1" val="$2"
  if grep -qE "^$key=" .env; then
    KEY="$key" VAL="$val" perl -pi -e 'BEGIN{$k=$ENV{KEY};$v=$ENV{VAL}} s/^\Q$k\E=.*/$k=$v/' .env
  else
    printf '%s=%s\n' "$key" "$val" >> .env
  fi
}
set_env SETUP_COMPLETE true
set_env COMPOSE_PROJECT_NAME "$PROJECT_NAME"

# ── 5. Reset CHANGELOG ─────────────────────────────────────────────────────────
cat > CHANGELOG.md <<'CHANGELOG'
# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
CHANGELOG

# ── 6. Summary ─────────────────────────────────────────────────────────────────
case "$PROFILE" in
  python-api)   enabled="Python · FastAPI · PostgreSQL · Redis"; disabled="Java · Go · Frontend · Kafka" ;;
  java-service) enabled="Python · Java · PostgreSQL · Redis · Kafka"; disabled="Go · Frontend" ;;
  go-worker)    enabled="Python · Go · PostgreSQL · Redis · Kafka"; disabled="Java · Frontend" ;;
  frontend)     enabled="Python · Next.js · PostgreSQL · Redis"; disabled="Java · Go" ;;
  full)         enabled="Python · Java · Go · Next.js · full stack"; disabled="(none)" ;;
esac

cat <<SUMMARY

─────────────────────────────────────────
Template initialised
─────────────────────────────────────────
Project:   $PROJECT_NAME
Org:       $ORG
Registry:  $REGISTRY
Profile:   $PROFILE

Enabled:   $enabled
Disabled:  $disabled

Remaining manual steps (3):
  1. Add GitHub Actions secrets: REGISTRY_USERNAME, REGISTRY_PASSWORD
  2. Add GitHub Actions variables: CONTAINER_REGISTRY, STAGING_BASE_URL
  3. Review .github/CODEOWNERS — verify team handles are correct

Next steps:
  make doctor
  make setup-core
  make smoke
─────────────────────────────────────────
SUMMARY
