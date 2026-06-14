#!/usr/bin/env python3
"""Verify the service-catalog traceability chain is internally consistent (Wave 1).

services.yaml is the canonical service registry (CLAUDE.md §0.1). It points at ADRs, Kafka topics,
Avro schemas, and (transitively, via type) per-service SLO files. Every one of those references is
a promise that something exists elsewhere in the repo. A dangling reference — an ADR that was
renumbered, a topic typo'd in a `subscribes:` list, a schema path that drifted — survives review
because nothing checks it. For an agentic system that reads this registry to plan work, a broken
reference propagates into specs and code. This gate makes the registry self-consistent.

Checks (all deterministic):
  1. ADR refs        — every `adr:` entry resolves to a docs/adr/ADR-<n>*.md file.
  2. Topic schemas   — every topic's `schema:` path exists on disk.
  3. Topic integrity — every topic in any service's publishes/subscribes is a defined topic.
  4. depends_on      — every depends_on target is a defined service.
  5. SLO presence    — every type:api service has a per-service SLO file (detail lives in
                       check_service_slo_files.py; here we assert presence to complete the chain).

Usage:
    python3 scripts/governance/check_traceability.py

Exit 0 = the chain is consistent; exit 1 = at least one broken link (use as a CI gate).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SERVICES = _REPO_ROOT / "services.yaml"
_ADR_DIR = _REPO_ROOT / "docs" / "adr"
_SLO_DIR = _REPO_ROOT / "docs" / "sre" / "slo"

_ADR_REF = re.compile(r"ADR-(\d{4})")


def _adr_numbers_on_disk(adr_dir: Path) -> set[str]:
    numbers: set[str] = set()
    for f in adr_dir.glob("ADR-*.md"):
        m = _ADR_REF.match(f.name)
        if m:
            numbers.add(m.group(1))
    return numbers


def check(services_path: Path = _SERVICES) -> list[str]:
    """Return a list of human-readable problems; empty list means the chain is consistent."""
    problems: list[str] = []
    catalog = yaml.safe_load(services_path.read_text(encoding="utf-8")) or {}
    services = catalog.get("services") or []
    topics = catalog.get("topics") or []

    defined_services = {s.get("name") for s in services}
    defined_topics = {t.get("name") for t in topics}
    adrs_on_disk = _adr_numbers_on_disk(_ADR_DIR)

    # 1. ADR references
    for svc in services:
        name = svc.get("name")
        for adr in svc.get("adr") or []:
            m = _ADR_REF.search(str(adr))
            if not m:
                problems.append(f"service '{name}': unparseable ADR reference {adr!r}.")
                continue
            if m.group(1) not in adrs_on_disk:
                problems.append(f"service '{name}': ADR-{m.group(1)} has no file in docs/adr/.")

    # 2. Topic schema paths
    for topic in topics:
        tname = topic.get("name")
        schema = topic.get("schema")
        if not schema:
            problems.append(f"topic '{tname}': no schema declared.")
            continue
        if not (_REPO_ROOT / schema).is_file():
            problems.append(f"topic '{tname}': schema path does not exist -> {schema}")

    # 3. Publish/subscribe topic integrity
    for svc in services:
        name = svc.get("name")
        for direction in ("publishes", "subscribes"):
            for topic_ref in svc.get(direction) or []:
                if topic_ref not in defined_topics:
                    problems.append(
                        f"service '{name}': {direction} undefined topic '{topic_ref}' "
                        f"(not in services.yaml topics)."
                    )

    # 4. depends_on integrity
    for svc in services:
        name = svc.get("name")
        for dep in svc.get("depends_on") or []:
            if dep not in defined_services:
                problems.append(f"service '{name}': depends_on undefined service '{dep}'.")

    # 5. SLO presence for canary-deployable (type: api) services
    for svc in services:
        name = svc.get("name")
        if svc.get("type") == "api" and not (_SLO_DIR / f"{name}.yaml").is_file():
            problems.append(
                f"service '{name}': missing docs/sre/slo/{name}.yaml "
                f"(see check_service_slo_files.py — ADR-0073)."
            )

    return problems


def main(argv: list[str] | None = None) -> int:
    problems = check()
    if problems:
        print("Traceability check FAILED — broken link(s) in services.yaml chain:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "\nFix the reference or add the missing artifact. "
            "Matrix: docs/governance/traceability-matrix.md.",
            file=sys.stderr,
        )
        return 1
    print("OK — service catalog traceability chain is consistent (ADRs, topics, schemas, deps).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
