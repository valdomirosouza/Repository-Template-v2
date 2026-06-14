#!/usr/bin/env python3
"""Fail if a canary-deployable service lacks a valid per-service SLO file (ADR-0073).

`cd-production.yml` resolves `docs/sre/slo/<service>.yaml` at deploy time and reads its `canary`
block (error_rate_max / p99_latency_seconds_max / error_budget_min_ratio). A service WITHOUT that
file fails the pipeline at deploy time — late, manual, and only for the one service being shipped.
This gate moves that failure left: it checks, on every PR, that EVERY canary-deployable service in
services.yaml has an SLO file with a well-formed canary block.

Canary-deployable = a service with `type: api` (HTTP services whose canary gate is expressed in
5xx error rate and p99 latency). Workers, jobs, and the static frontend deploy by other paths and
are intentionally out of scope here.

Each required file must satisfy docs/sre/slo/schema/service-slo.schema.json:
  - top-level `service` matching the services.yaml name
  - `canary.error_rate_max`         number in (0, 1]
  - `canary.p99_latency_seconds_max` number > 0
  - `canary.error_budget_min_ratio` number in (0, 1]

Usage:
    python3 scripts/governance/check_service_slo_files.py

Exit 0 = every canary-deployable service has a valid SLO file; exit 1 = at least one is missing or
malformed (use as a CI gate).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SERVICES = _REPO_ROOT / "services.yaml"
_SLO_DIR = _REPO_ROOT / "docs" / "sre" / "slo"

# Service types whose production rollout goes through the SLO-gated canary in cd-production.yml.
_CANARY_TYPES = {"api"}
_REQUIRED_CANARY_KEYS = ("error_rate_max", "p99_latency_seconds_max", "error_budget_min_ratio")


def _is_ratio(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value <= 1


def _is_positive(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def check(services_path: Path = _SERVICES, slo_dir: Path = _SLO_DIR) -> list[str]:
    """Return a list of human-readable problems; empty list means all good."""
    problems: list[str] = []
    catalog = yaml.safe_load(services_path.read_text(encoding="utf-8")) or {}
    services = catalog.get("services") or []

    for svc in services:
        name = svc.get("name")
        if svc.get("type") not in _CANARY_TYPES:
            continue
        slo_file = slo_dir / f"{name}.yaml"
        try:
            rel = slo_file.relative_to(_REPO_ROOT)
        except ValueError:
            rel = slo_file  # slo_dir outside the repo (e.g. under test) — show the full path
        if not slo_file.exists():
            problems.append(
                f"{name}: missing canary SLO file {rel} "
                f"(cd-production.yml would block this service's rollout — ADR-0073)."
            )
            continue
        try:
            doc = yaml.safe_load(slo_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            problems.append(f"{rel}: invalid YAML ({exc}).")
            continue

        if doc.get("service") != name:
            problems.append(
                f"{rel}: top-level `service` should be '{name}', got {doc.get('service')!r}."
            )

        canary = doc.get("canary")
        if not isinstance(canary, dict):
            problems.append(f"{rel}: missing `canary` block (ADR-0073).")
            continue
        for key in _REQUIRED_CANARY_KEYS:
            if key not in canary:
                problems.append(f"{rel}: canary.{key} is missing (ADR-0073).")

        if "error_rate_max" in canary and not _is_ratio(canary["error_rate_max"]):
            problems.append(f"{rel}: canary.error_rate_max must be a number in (0, 1].")
        p99 = canary.get("p99_latency_seconds_max")
        if "p99_latency_seconds_max" in canary and not _is_positive(p99):
            problems.append(f"{rel}: canary.p99_latency_seconds_max must be a number > 0.")
        if "error_budget_min_ratio" in canary and not _is_ratio(canary["error_budget_min_ratio"]):
            problems.append(f"{rel}: canary.error_budget_min_ratio must be a number in (0, 1].")

    return problems


def main(argv: list[str] | None = None) -> int:
    problems = check()
    if problems:
        print("Per-service SLO file check FAILED (ADR-0073):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "\nAdd/repair docs/sre/slo/<service>.yaml "
            "(schema: docs/sre/slo/schema/service-slo.schema.json).",
            file=sys.stderr,
        )
        return 1
    print("OK — every canary-deployable (type: api) service has a valid per-service SLO file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
