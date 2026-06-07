#!/usr/bin/env bash
# new-service.sh — scaffold a new service and (optionally) self-register it.
#
#   scripts/new-service.sh NAME LANG [OWNER] [PORT] [REGISTER]
#     LANG     = python | java | go
#     OWNER    = CODEOWNERS team (default: platform-team)
#     PORT     = primary port (default: 8010)
#     REGISTER = true|false (default: false)
#
# Generation is delegated to scaffold/scaffold.py (templates in scaffold/templates/).
# When REGISTER=true, also updates services.yaml, .github/CODEOWNERS, and the Prometheus
# scrape config. Reusability Uplift v2.0.0 (ADR-0059). Spec: Improvement 10.
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1

NAME="${1:-}"
LANG="${2:-}"
OWNER="${3:-platform-team}"
PORT="${4:-8010}"
REGISTER="${5:-false}"

if [ -z "$NAME" ] || [ -z "$LANG" ]; then
  echo "Usage: new-service.sh NAME LANG [OWNER] [PORT] [REGISTER]" >&2
  exit 1
fi
case "$LANG" in python|java|go) ;; *) echo "ERROR: LANG must be python|java|go" >&2; exit 1 ;; esac

# ── Generate from template ─────────────────────────────────────────────────────
python3 scaffold/scaffold.py --name "$NAME" --lang "$LANG"

if [ "$REGISTER" != "true" ]; then
  cat <<MANUAL

Service scaffolded: services/$NAME/
To register it, run:
  make new-service NAME=$NAME LANG=$LANG REGISTER=true
Or manually update:
  services.yaml
  .github/CODEOWNERS
  infrastructure/monitoring/prometheus/prometheus.yml
MANUAL
  exit 0
fi

echo "Registering '$NAME'…"

case "$LANG" in
  go) TYPE="worker" ;;
  *)  TYPE="api" ;;
esac

# ── 1. services.yaml — insert a new entry before the `topics:` block ────────────
NAME="$NAME" LANG="$LANG" TYPE="$TYPE" PORT="$PORT" OWNER="$OWNER" python3 - <<'PY'
import os, pathlib
p = pathlib.Path("services.yaml")
lines = p.read_text().splitlines(keepends=True)
entry = (
    f"\n  - name: {os.environ['NAME']}\n"
    f"    language: {os.environ['LANG']}\n"
    f"    type: {os.environ['TYPE']}\n"
    f"    port: {os.environ['PORT']}\n"
    f"    image: {os.environ['NAME']}\n"
    f"    owner: {os.environ['OWNER']}\n"
    f"    adr: []\n"
)
out, inserted = [], False
for line in lines:
    if not inserted and line.startswith("topics:"):
        out.append(entry + "\n")
        inserted = True
    out.append(line)
if not inserted:
    out.append(entry)
p.write_text("".join(out))
print("  services.yaml: entry added")
PY

# ── 2. CODEOWNERS — add an ownership line ───────────────────────────────────────
ORG="$(grep -oE '@[A-Za-z0-9_-]+/' .github/CODEOWNERS | head -1 | tr -d '@/')"
ORG="${ORG:-your-org}"
printf '\n/services/%s/    @%s/%s\n' "$NAME" "$ORG" "$OWNER" >> .github/CODEOWNERS
echo "  CODEOWNERS: /services/$NAME/ → @$ORG/$OWNER"

# ── 3. Prometheus scrape job ────────────────────────────────────────────────────
cat >> infrastructure/monitoring/prometheus/prometheus.yml <<SCRAPE

  - job_name: $NAME
    metrics_path: /metrics
    static_configs:
      - targets: ["host.docker.internal:$PORT"]
SCRAPE
echo "  prometheus.yml: scrape job for $NAME (:$PORT)"

cat <<DONE

Registered '$NAME'. Review the generated files and the registry edits, then commit.
Next: add a K8s manifest under infrastructure/k8s/ if this service deploys to a cluster.
DONE
