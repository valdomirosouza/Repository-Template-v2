#!/usr/bin/env bash
# vcs.sh — the one place agents, skills and scripts talk to the VCS host (W14-T6, issue #381).
#
# The Seven-Axis Review counted 37 direct `gh` invocations across .claude/, skills/ and scripts/.
# Every one now goes through this shim, so porting to another host is one file, and the set of
# verbs the delivery workflow depends on is explicit. GitHub Actions workflows keep calling `gh`
# directly — they run on GitHub by definition.
#
# Usage:  scripts/vcs.sh <noun> <verb> [args…]      (args are passed through unchanged)
#   issue  create|list|edit|view|comment|close
#   pr     create|view|list|edit|ready|merge|comment|checks|diff|review
#   release create|view
#   api    <endpoint> [args…]
#   repo   view
#
# Provider selection: VCS_PROVIDER=github (default). Any other value fails loudly with the
# verb that would need a port — see CUSTOMISING.md §"GitHub-only governance".
set -euo pipefail

provider="${VCS_PROVIDER:-github}"
noun="${1:-}"; verb="${2:-}"
if [ -z "$noun" ] || [ -z "$verb" ]; then
  echo "usage: scripts/vcs.sh <issue|pr|release|api|repo> <verb> [args…]" >&2
  exit 64
fi
shift 2

case "$provider" in
  github)
    command -v gh >/dev/null 2>&1 || { echo "vcs.sh: gh CLI not installed (VCS_PROVIDER=github)" >&2; exit 69; }
    case "$noun" in
      issue|pr|release|repo) exec gh "$noun" "$verb" "$@" ;;
      api)                   exec gh api "$verb" "$@" ;;
      *) echo "vcs.sh: unknown noun '$noun'" >&2; exit 64 ;;
    esac
    ;;
  *)
    echo "vcs.sh: VCS_PROVIDER='$provider' has no implementation for '$noun $verb'." >&2
    echo "        Port this verb in scripts/vcs.sh (see CUSTOMISING.md §GitHub-only governance)." >&2
    exit 70
    ;;
esac
