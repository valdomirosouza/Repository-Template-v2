#!/usr/bin/env bash
# check-template-placeholders.sh — detect unresolved template placeholder strings.
#
# Scans tracked text files for placeholders that `make template-init` is meant to
# replace. Each hit is an ERROR (exit 1) — except `placeholder-set-in-env`, which is
# only a WARNING when AI_AGENTS_ENABLED is not true (a non-AI adopter may legitimately
# leave the LLM key as a placeholder).
#
# Skips binary files (git grep -I) and this script itself (it contains the literals).
#
# Reusability Uplift v2.0.0 (ADR-0059). Spec: reusability-uplift-v2.0.0.md Improvement 3.
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

if [ -t 1 ]; then
  RED=$'\033[0;31m'; YELLOW=$'\033[0;33m'; GREEN=$'\033[0;32m'; RESET=$'\033[0m'
else
  RED=""; YELLOW=""; GREEN=""; RESET=""
fi

SELF="scripts/check-template-placeholders.sh"

# Placeholders that always indicate an uninitialised template.
ERROR_PLACEHOLDERS=(
  "@your-org/"
  "yourorg/"
  "template-service"
  "com.yourorg"
  "github.com/yourorg"
)
# Hint shown per placeholder.
hint_for() {
  case "$1" in
    "@your-org/")        echo "Replace with your GitHub org handle in .github/CODEOWNERS." ;;
    "yourorg/")          echo "Replace with your container registry namespace." ;;
    "template-service")  echo "Replace with your project name." ;;
    "com.yourorg")       echo "Replace with your Java package root." ;;
    "github.com/yourorg") echo "Replace with your Go module path / org." ;;
    "placeholder-set-in-env") echo "Set a real value in .env (only required when AI_AGENTS_ENABLED=true)." ;;
    *) echo "Replace with your project value." ;;
  esac
}

ai_enabled="false"
if [ -f .env ] && grep -q '^AI_AGENTS_ENABLED=true' .env 2>/dev/null; then
  ai_enabled="true"
fi

errors=0
warnings=0

report() {
  # report SEVERITY PLACEHOLDER "file:line"
  local sev="$1" ph="$2" loc="$3" colour label
  if [ "$sev" = "ERROR" ]; then colour="$RED"; label="ERROR"; else colour="$YELLOW"; label="WARNING"; fi
  printf '%s%s: Template placeholder found%s\n' "$colour" "$label" "$RESET"
  printf '  String:  %s\n' "$ph"
  printf '  File:    %s\n' "$loc"
  printf '  Action:  %s\n\n' "$(hint_for "$ph")"
}

scan() {
  # scan SEVERITY PLACEHOLDER
  local sev="$1" ph="$2" line
  # -I skips binaries; -n line numbers; -F fixed string. Exclude this script.
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in
      "$SELF":*) continue ;;
    esac
    report "$sev" "$ph" "$line"
    if [ "$sev" = "ERROR" ]; then errors=$((errors + 1)); else warnings=$((warnings + 1)); fi
  done < <(git grep -I -n -F -e "$ph" -- . ':!'"$SELF" 2>/dev/null || true)
}

for ph in "${ERROR_PLACEHOLDERS[@]}"; do
  scan "ERROR" "$ph"
done

# LLM placeholder: WARNING unless AI agents are enabled.
if [ "$ai_enabled" = "true" ]; then
  scan "ERROR" "placeholder-set-in-env"
else
  scan "WARNING" "placeholder-set-in-env"
fi

echo "-------------------------------------------"
printf 'Placeholders: %s error(s), %s warning(s).\n' "$errors" "$warnings"
if [ "$errors" -gt 0 ]; then
  echo "${RED}Run 'make template-init PROJECT_NAME=<n> ORG=<o> REGISTRY=<r>' to resolve.${RESET}"
  exit 1
fi
echo "${GREEN}No blocking template placeholders found.${RESET}"
