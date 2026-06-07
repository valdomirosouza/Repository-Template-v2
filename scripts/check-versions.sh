#!/usr/bin/env bash
# check-versions.sh — verify installed runtimes meet the template's minimum versions.
#
# Prints a coloured pass/fail line per runtime and exits 1 if any installed runtime
# is below its minimum (or missing, when the runtime is required). Optional runtimes
# (java/go/node) that are absent are reported as a skip, not a failure — a Python-only
# adopter does not need them.
#
# Reusability Uplift v2.0.0 (ADR-0059). Spec: reusability-uplift-v2.0.0.md Improvement 1.
set -euo pipefail

# ── Minimums (keep in sync with .devcontainer, Dockerfiles, README matrix) ──────
PY_MIN="3.13"
JAVA_MIN="21"
GO_MIN="1.24"
NODE_MIN="22"
UV_MIN="0.4"

if [ -t 1 ]; then
  GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; YELLOW=$'\033[0;33m'; RESET=$'\033[0m'
else
  GREEN=""; RED=""; YELLOW=""; RESET=""
fi

fail=0

# ver_ge A B → true if A >= B (semantic-ish, via sort -V)
ver_ge() {
  [ "$1" = "$2" ] && return 0
  local lowest
  lowest="$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)"
  [ "$lowest" = "$2" ]
}

# check NAME REQUIRED(yes|no) MIN VERSION_CMD
check() {
  local name="$1" required="$2" min="$3" cmd="$4" got
  if ! command -v "${cmd%% *}" >/dev/null 2>&1; then
    if [ "$required" = "yes" ]; then
      printf '%s✗ FAIL%s  %-7s missing (need >= %s)\n' "$RED" "$RESET" "$name" "$min"
      fail=1
    else
      printf '%s‒ SKIP%s  %-7s not installed (optional, need >= %s)\n' "$YELLOW" "$RESET" "$name" "$min"
    fi
    return
  fi
  got="$(eval "$5" 2>/dev/null || true)"
  # A non-numeric result means the launcher exists but no real runtime is present
  # (e.g. the macOS `java` stub). Treat as missing.
  if ! printf '%s' "$got" | grep -qE '^[0-9]'; then
    got=""
  fi
  if [ -z "$got" ]; then
    if [ "$required" = "yes" ]; then
      printf '%s✗ FAIL%s  %-7s missing/undetectable (need >= %s)\n' "$RED" "$RESET" "$name" "$min"
      fail=1
    else
      printf '%s‒ SKIP%s  %-7s not installed (optional, need >= %s)\n' "$YELLOW" "$RESET" "$name" "$min"
    fi
  elif ver_ge "$got" "$min"; then
    printf '%s✓ PASS%s  %-7s %s (>= %s)\n' "$GREEN" "$RESET" "$name" "$got" "$min"
  else
    printf '%s✗ FAIL%s  %-7s %s (need >= %s)\n' "$RED" "$RESET" "$name" "$got" "$min"
    fail=1
  fi
}

echo "Runtime versions (minimums for Repository-Template-v2):"
echo

check Python yes "$PY_MIN" python3 \
  "python3 -c 'import platform; print(platform.python_version())'"
check uv     yes "$UV_MIN" uv \
  "uv --version | awk '{print \$2}'"
check Node   no  "$NODE_MIN" node \
  "node --version | sed 's/^v//'"
check Go     no  "$GO_MIN" go \
  "go version | awk '{print \$3}' | sed 's/^go//'"
check Java   no  "$JAVA_MIN" java \
  "java -version 2>&1 | head -1 | sed -E 's/.*\"([0-9]+).*/\\1/'"

echo
if [ "$fail" -ne 0 ]; then
  echo "${RED}Some required runtimes are missing or below the minimum.${RESET}"
  exit 1
fi
echo "${GREEN}All required runtimes meet the minimum versions.${RESET}"
