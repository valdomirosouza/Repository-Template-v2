#!/usr/bin/env python3
"""Shared state/context store for the Agentic Spec-Driven Delivery agent system.

The orchestrator and the 15 phase subagents (`.claude/agents/`) pass a single shared
context object through the lifecycle. This script is the deterministic, runnable
persistence layer the agents call via Bash:

    python scripts/asdd_state.py init --feature FEAT-42 --title "Bulk HITL approve" \
        --risk-class "normal feature"
    python scripts/asdd_state.py append-handoff --feature FEAT-42 \
        --status done --phase 0 --agent asdd-phase-0-intake \
        --artifacts intake-form.md --handoff-to asdd-phase-1-conception --notes "..."
    python scripts/asdd_state.py show --feature FEAT-42

State is persisted at `.agent/delivery/<feature_id>/state.json` (gitignored — it is
per-run delivery state, not source).

Handoff message contract (also see docs/sdlc/agent-handoff-schema.md):
    { status, phase, agent, artifacts[], handoff_to, reason, notes, human_gate, timestamp }

Governance: a `human_gate: true` handoff means the next phase requires explicit human
approval before the orchestrator may proceed. Agents never auto-execute irreversible
real-world effects (deploy/release/autonomy changes) — they prepare and recommend.

Spec:  docs/sdlc/agentic-spec-driven-delivery.md
ADR:   ADR-0058
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

VALID_STATUS = ("done", "blocked")
MIN_PHASE = 0
MAX_PHASE = 14


def _now() -> str:
    return datetime.now(UTC).isoformat()


def state_path(feature_id: str, root: Path | None = None) -> Path:
    """Return the on-disk path of a feature's shared-state file."""
    return (root or ROOT) / ".agent" / "delivery" / feature_id / "state.json"


def init_state(
    feature_id: str,
    title: str,
    risk_class: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Create (or reset) the shared state for a feature and return it."""
    state: dict[str, Any] = {
        "schema_version": "asdd_state_v1",
        "feature_id": feature_id,
        "title": title,
        "risk_class": risk_class,
        "current_phase": 0,
        "blocked": False,
        "started_at": _now(),
        "updated_at": _now(),
        "artifacts": {},
        "handoffs": [],
    }
    path = state_path(feature_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def load_state(feature_id: str, root: Path | None = None) -> dict[str, Any]:
    """Load a feature's shared state. Raises FileNotFoundError if not initialized."""
    path = state_path(feature_id, root)
    if not path.exists():
        raise FileNotFoundError(
            f"No delivery state for '{feature_id}' — run `asdd_state.py init` first."
        )
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def validate_handoff(handoff: dict[str, Any]) -> list[str]:
    """Return a list of validation errors for a handoff message (empty == valid)."""
    errors: list[str] = []
    status = handoff.get("status")
    if status not in VALID_STATUS:
        errors.append(f"status must be one of {VALID_STATUS}, got {status!r}")
    phase = handoff.get("phase")
    if not isinstance(phase, int) or not (MIN_PHASE <= phase <= MAX_PHASE):
        errors.append(f"phase must be an int in [{MIN_PHASE}, {MAX_PHASE}], got {phase!r}")
    if not handoff.get("agent"):
        errors.append("agent is required")
    if not isinstance(handoff.get("artifacts", []), list):
        errors.append("artifacts must be a list")
    if status == "blocked" and not handoff.get("reason"):
        errors.append("reason is required when status == 'blocked'")
    if "handoff_to" not in handoff:
        errors.append("handoff_to is required")
    return errors


def append_handoff(
    feature_id: str,
    handoff: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    """Validate + append a handoff to the feature state, updating phase/blocked flags.

    Raises ValueError on an invalid handoff (fail-closed).
    """
    errors = validate_handoff(handoff)
    if errors:
        raise ValueError("invalid handoff: " + "; ".join(errors))

    state = load_state(feature_id, root)
    handoff.setdefault("timestamp", _now())
    handoff.setdefault("human_gate", False)
    state["handoffs"].append(handoff)
    state["current_phase"] = handoff["phase"]
    state["blocked"] = handoff["status"] == "blocked"
    state["updated_at"] = _now()
    for art in handoff.get("artifacts", []):
        # index artifacts by basename stem for quick lookup by later phases
        state["artifacts"][Path(art).name] = art

    state_path(feature_id, root).write_text(json.dumps(state, indent=2) + "\n")
    return state


# ── CLI ─────────────────────────────────────────────────────────────────────


def _cmd_init(args: argparse.Namespace) -> int:
    init_state(args.feature, args.title, args.risk_class)
    print(f"Initialized delivery state for {args.feature} at {state_path(args.feature)}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    print(json.dumps(load_state(args.feature), indent=2))
    return 0


def _cmd_append(args: argparse.Namespace) -> int:
    handoff = {
        "status": args.status,
        "phase": args.phase,
        "agent": args.agent,
        "artifacts": args.artifacts or [],
        "handoff_to": args.handoff_to,
        "reason": args.reason or "",
        "notes": args.notes or "",
        "human_gate": args.human_gate,
    }
    errors = validate_handoff(handoff)
    if errors:
        for e in errors:
            print(f"::error::{e}", file=sys.stderr)
        return 1
    append_handoff(args.feature, handoff)
    gate = " [HUMAN GATE]" if args.human_gate else ""
    print(f"Recorded {args.status} handoff for phase {args.phase} ({args.agent}){gate}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agentic Spec-Driven Delivery shared state.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize feature delivery state")
    p_init.add_argument("--feature", required=True)
    p_init.add_argument("--title", required=True)
    p_init.add_argument("--risk-class", required=True, dest="risk_class")
    p_init.set_defaults(func=_cmd_init)

    p_show = sub.add_parser("show", help="print feature delivery state")
    p_show.add_argument("--feature", required=True)
    p_show.set_defaults(func=_cmd_show)

    p_app = sub.add_parser("append-handoff", help="validate + append a phase handoff")
    p_app.add_argument("--feature", required=True)
    p_app.add_argument("--status", required=True, choices=VALID_STATUS)
    p_app.add_argument("--phase", required=True, type=int)
    p_app.add_argument("--agent", required=True)
    p_app.add_argument("--artifacts", nargs="*", default=[])
    p_app.add_argument("--handoff-to", required=True, dest="handoff_to")
    p_app.add_argument("--reason", default="")
    p_app.add_argument("--notes", default="")
    p_app.add_argument("--human-gate", action="store_true", dest="human_gate")
    p_app.set_defaults(func=_cmd_append)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
