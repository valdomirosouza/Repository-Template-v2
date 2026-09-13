#!/usr/bin/env bash
# doctor.sh — validate the local environment before setup.
#
# Prints a coloured PASS/FAIL (or WARN) line per check with a "how to fix" hint on
# failure. Required tools (git, gh, uv, python, docker) fail the run; optional language
# runtimes (node, go, java) warn. Ports warn only (conflicts are recoverable).
# Exits 1 if any required check fails.
#
# Reusability Uplift v2.0.0 (ADR-0059). Spec: reusability-uplift-v2.0.0.md Improvement 4.
set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1

if [ -t 1 ]; then
  GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; YELLOW=$'\033[0;33m'; RESET=$'\033[0m'
else
  GREEN=""; RED=""; YELLOW=""; RESET=""
fi

fail=0

pass() { printf '%s✓ PASS%s  %s\n' "$GREEN" "$RESET" "$1"; }
warn() { printf '%s! WARN%s  %s\n' "$YELLOW" "$RESET" "$1"; }
err()  { printf '%s✗ FAIL%s  %s\n         ↳ %s\n' "$RED" "$RESET" "$1" "$2"; fail=1; }

ver_ge() {
  [ "$1" = "$2" ] && return 0
  [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

# tool_check NAME REQUIRED(yes|no) MIN VERSION_CMD FIX
tool_check() {
  local name="$1" required="$2" min="$3" vcmd="$4" fix="$5" got
  if ! command -v "$name" >/dev/null 2>&1; then
    if [ "$required" = "yes" ]; then err "$name missing (need >= $min)" "$fix"
    else warn "$name not installed (optional, need >= $min)"; fi
    return
  fi
  got="$(eval "$vcmd" 2>/dev/null || true)"
  if ! printf '%s' "$got" | grep -qE '^[0-9]'; then got=""; fi
  if [ -z "$got" ]; then
    if [ "$required" = "yes" ]; then err "$name version undetectable" "$fix"; else warn "$name version undetectable"; fi
  elif ver_ge "$got" "$min"; then pass "$name $got (>= $min)"
  else
    if [ "$required" = "yes" ]; then err "$name $got (need >= $min)" "$fix"; else warn "$name $got (need >= $min)"; fi
  fi
}

# Minimums come from versions.yaml (W14-T2); fall back to the last known values offline.
_v() { python3 scripts/governance/check_toolchain_versions.py --print "$1" minimum 2>/dev/null || echo "$2"; }
echo "── Tools ──────────────────────────────────────────────"
tool_check git    yes 2.40 "git --version | awk '{print \$3}'"                 "Install from https://git-scm.com"
tool_check gh     yes 2.40 "gh --version | head -1 | awk '{print \$3}'"        "Install from https://cli.github.com"
tool_check uv     yes "$(_v uv 0.4)"  "uv --version | awk '{print \$2}'"       "pip install uv"
tool_check python3 yes "$(_v python 3.13)" "python3 -c 'import platform;print(platform.python_version())'" "uv python install 3.13"
tool_check node   no  "$(_v node 22)" "node --version | sed 's/^v//'"          "nvm install 22"
tool_check go     no  "$(_v go 1.26)" "go version | awk '{print \$3}' | sed 's/^go//'" "Install from https://go.dev/dl"
tool_check java   no  "$(_v java 21)" "java -version 2>&1 | head -1 | sed -E 's/.*\"([0-9]+).*/\\1/'" "sdk install java 21-tem"
# W14-T7 (issue #382): the Makefile needs these too; doctor used to stay silent about them.
tool_check pnpm   no  9    "pnpm --version"                                      "npm i -g pnpm@9"
tool_check mvn    no  3.9  "mvn --version 2>/dev/null | head -1 | awk '{print \$3}'" "sdk install maven"
tool_check helm   no  3.14 "helm version --short 2>/dev/null | sed -E 's/^v([0-9.]+).*/\\1/'" "Install from https://helm.sh"
tool_check kubectl no 1.29 "kubectl version --client -o json 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"clientVersion\"][\"gitVersion\"].lstrip(\"v\"))'" "Install from https://kubernetes.io"
tool_check syft   no  1.0  "syft version 2>/dev/null | awk '/^Version:/{print \$2}'" "Install from https://github.com/anchore/syft"
tool_check cosign no  2.0  "cosign version 2>/dev/null | awk '/GitVersion:/{print \$2}' | sed 's/^v//'" "Install from https://github.com/sigstore/cosign"
tool_check trivy  no  0.50 "trivy --version 2>/dev/null | awk '/^Version:/{print \$2}'" "Install from https://trivy.dev"
tool_check protoc no  25   "protoc --version 2>/dev/null | awk '{print \$2}'"   "Install protobuf-compiler"

echo
echo "── Docker ─────────────────────────────────────────────"
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then pass "Docker daemon running"
  else err "Docker daemon not running" "Start Docker Desktop, or run 'colima start'"; fi
  if docker compose version >/dev/null 2>&1; then
    cv="$(docker compose version --short 2>/dev/null | sed 's/^v//')"
    if [ -n "$cv" ] && ver_ge "$cv" 2.20; then pass "docker compose $cv (>= 2.20)"
    else warn "docker compose $cv (need >= 2.20)"; fi
  else err "docker compose plugin missing" "Install Docker Desktop or the Compose plugin"; fi
else
  err "docker missing" "Install Docker Desktop or Colima"
fi

echo
echo "── Environment ────────────────────────────────────────"
if [ -f .env ]; then
  pass ".env exists"
  sk="$(grep -E '^SECRET_KEY=' .env | head -1 | cut -d= -f2-)"
  if [ -n "$sk" ] && ! printf '%s' "$sk" | grep -qi 'placeholder'; then pass "SECRET_KEY is set"
  else err "SECRET_KEY not set (placeholder/empty)" "Generate: openssl rand -hex 32, then set SECRET_KEY in .env"; fi
  if grep -qE '^AI_AGENTS_ENABLED=' .env; then pass "AI_AGENTS_ENABLED defined"
  else warn "AI_AGENTS_ENABLED not defined in .env (defaults to false)"; fi
  if grep -qE '^AI_AGENTS_ENABLED=true' .env; then
    lk="$(grep -E '^(LLM_API_KEY|ANTHROPIC_API_KEY)=' .env | head -1 | cut -d= -f2-)"
    if [ -n "$lk" ] && ! printf '%s' "$lk" | grep -qi 'placeholder'; then pass "LLM key set (AI agents enabled)"
    else err "AI_AGENTS_ENABLED=true but LLM key unset" "Set LLM_API_KEY in .env, or set AI_AGENTS_ENABLED=false"; fi
  fi
else
  err ".env missing" "Run 'cp .env.example .env' (make template-init does this for you)"
fi

echo
echo "── Ports (warn only) ──────────────────────────────────"
check_port() {
  local p="$1" what="$2"
  if ! command -v lsof >/dev/null 2>&1; then
    warn "port $p not checked ($what) — lsof missing, cannot tell whether it is free"  # W14-T7: no false PASS
    return
  fi
  if lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "port $p in use ($what) — override via .env or stop the other service"
  else pass "port $p free ($what)"; fi
}
check_port 3000  "frontend dev"
check_port 8000  "API"
check_port 5432  "PostgreSQL"
check_port 6379  "Redis"
check_port 9092  "Kafka"
check_port 9090  "Prometheus"
check_port 3001  "Grafana"
check_port 16686 "Jaeger"

echo
echo "── Template placeholders ──────────────────────────────"
if bash scripts/check-template-placeholders.sh >/dev/null 2>&1; then
  pass "no blocking template placeholders"
else
  err "unresolved template placeholders" "Run 'make template-init PROJECT_NAME=x ORG=y REGISTRY=z' to resolve"
fi

echo
echo "───────────────────────────────────────────────────────"
if [ "$fail" -ne 0 ]; then
  echo "${RED}Environment has problems — fix the FAIL items above, then re-run 'make doctor'.${RESET}"
  exit 1
fi
echo "${GREEN}Environment looks good. Next: make setup-core (or make setup-minimal).${RESET}"
