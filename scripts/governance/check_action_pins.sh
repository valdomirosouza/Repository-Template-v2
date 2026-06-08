#!/usr/bin/env bash
# Fail if any GitHub Actions `uses:` reference is not pinned to a full 40-char commit SHA.
# Supply-chain hardening (RFC-0015): mutable tags (@v4, @main) are a CI compromise vector.
# Local actions/reusable workflows (uses: ./...) and docker-digest refs (@sha256:...) are allowed.
set -euo pipefail

WORKFLOW_DIR="${1:-.github/workflows}"

# Lines like `uses: owner/repo@<ref>` that are NOT 40-hex-SHA-pinned, NOT local (./),
# and NOT docker-digest (@sha256:).
unpinned="$(grep -rhnE '^[[:space:]]*-?[[:space:]]*uses:[[:space:]]' "$WORKFLOW_DIR" \
  | grep -vE 'uses:[[:space:]]+\./' \
  | grep -vE 'uses:[[:space:]]+[^@]+@[0-9a-f]{40}([[:space:]]|$)' \
  | grep -vE 'uses:[[:space:]]+docker://[^@]+@sha256:' \
  || true)"

if [ -n "$unpinned" ]; then
  echo "::error::Unpinned GitHub Actions found — pin to a full commit SHA (RFC-0015):"
  echo "$unpinned"
  exit 1
fi

echo "✅ All GitHub Actions in $WORKFLOW_DIR are SHA-pinned."
