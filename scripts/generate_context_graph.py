#!/usr/bin/env python3
"""Generate `.agent/context-graph.json` — a compact repo map for agent bootstrap.

Instead of an agent reading many documents at session start, this script produces a
single small JSON that maps the repository's governance and implementation surface:

  - specs     → implementation files that reference each spec
  - adrs      → ADR id/title + files affected by each ADR
  - skills    → skill files and their trigger domain
  - services  → services.yaml entries (apis, topics)
  - tools     → tool catalog risk policy (risk_level, requires_hitl, reversible, …)
  - features  → per-feature lifecycle state (docs/product/FEAT-*/state.yaml)
  - checksums → sha256 (truncated) of key governance files for drift detection

The output is intentionally small (< 50 KB target) so it fits an LLM bootstrap.
The mapping is derived from `Spec:`/`ADR:` references already present in source
docstrings, so it stays accurate without a separate registry.

Spec:  Agentic-SDLC-Repository-Improvement-Directive.md §7
ADR:   ADR-0057 (repository hygiene), ADR-0041 (context graph)
Usage: python scripts/generate_context_graph.py [--check] [--output PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".agent" / "context-graph.json"

# Files whose checksum is worth tracking for drift detection.
_KEY_FILES = (
    "version.txt",
    "pyproject.toml",
    "CLAUDE.md",
    "services.yaml",
    "infrastructure/agent-tools/tools.yaml",
    "docs/process/gates/phase-gates.yaml",
    "docs/process/WORKFLOW.md",
)

_SPEC_RE = re.compile(r"Spec:\s*(specs/[^\s,]+)")
_ADR_RE = re.compile(r"(ADR-\d{4})")
# Title separator may be em-dash (U+2014), en-dash (U+2013), or hyphen.
_ADR_TITLE_RE = re.compile(r"^#\s*(ADR-\d{4})\s*[\u2014\u2013-]\s*(.+?)\s*$", re.MULTILINE)


def _sha256_short(path: Path, length: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:length]


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _build_reference_maps(root: Path) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Scan src/ for `Spec:`/`ADR:` references → {spec: [files]}, {adr: [files]}."""
    spec_to_impl: dict[str, list[str]] = {}
    adr_to_impl: dict[str, list[str]] = {}
    src = root / "src"
    if not src.exists():
        return spec_to_impl, adr_to_impl
    for py in sorted(src.rglob("*.py")):
        try:
            text = py.read_text()
        except OSError:
            continue
        rel = _rel(py)
        for spec in set(_SPEC_RE.findall(text)):
            spec_to_impl.setdefault(spec, [])
            if rel not in spec_to_impl[spec]:
                spec_to_impl[spec].append(rel)
        # Only treat ADR refs in the top docstring region as "affected" to limit noise.
        head = text[:1500]
        for adr in set(_ADR_RE.findall(head)):
            adr_to_impl.setdefault(adr, [])
            if rel not in adr_to_impl[adr]:
                adr_to_impl[adr].append(rel)
    return spec_to_impl, adr_to_impl


def _collect_adrs(root: Path, adr_to_impl: dict[str, list[str]]) -> list[dict[str, Any]]:
    adr_dir = root / "docs" / "adr"
    adrs: list[dict[str, Any]] = []
    if not adr_dir.exists():
        return adrs
    for md in sorted(adr_dir.glob("ADR-*.md")):
        m = _ADR_TITLE_RE.search(md.read_text())
        if not m:
            continue
        adr_id, title = m.group(1), m.group(2)
        adrs.append(
            {
                "id": adr_id,
                "title": title,
                "path": _rel(md),
                "affects": sorted(adr_to_impl.get(adr_id, [])),
            }
        )
    return adrs


def _collect_specs(root: Path, spec_to_impl: dict[str, list[str]]) -> list[dict[str, Any]]:
    specs_dir = root / "specs"
    specs: list[dict[str, Any]] = []
    if not specs_dir.exists():
        return specs
    for spec in sorted(specs_dir.rglob("*.md")):
        rel = _rel(spec)
        specs.append({"path": rel, "implemented_by": sorted(spec_to_impl.get(rel, []))})
    return specs


def _collect_skills(root: Path) -> list[dict[str, str]]:
    skills_dir = root / "skills"
    skills: list[dict[str, str]] = []
    if not skills_dir.exists():
        return skills
    for md in sorted(skills_dir.rglob("*.md")):
        rel = _rel(md)
        # domain = parent directory under skills/ (e.g. sre, privacy, ai)
        parts = md.relative_to(skills_dir).parts
        domain = parts[0] if len(parts) > 1 else "general"
        skills.append({"path": rel, "domain": domain})
    return skills


def _collect_services(root: Path) -> list[dict[str, Any]]:
    path = root / "services.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    services = data.get("services", data) if isinstance(data, dict) else []
    out: list[dict[str, Any]] = []
    if isinstance(services, list):
        for s in services:
            if not isinstance(s, dict):
                continue
            out.append(
                {
                    "name": s.get("name"),
                    "language": s.get("language"),
                    "apis": s.get("apis", []),
                    "topics": s.get("topics", []),
                }
            )
    return out


def _collect_tools(root: Path) -> list[dict[str, Any]]:
    path = root / "infrastructure" / "agent-tools" / "tools.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    out: list[dict[str, Any]] = []
    for t in data.get("tools", []):
        out.append(
            {
                "name": t.get("name"),
                "risk_level": t.get("risk_level"),
                "requires_hitl": t.get("requires_hitl"),
                "reversible": t.get("reversible"),
                "max_hotl_risk_score": t.get("max_hotl_risk_score"),
                "requires_dual_approval": t.get("requires_dual_approval"),
            }
        )
    return out


def _collect_features(root: Path) -> list[dict[str, Any]]:
    product = root / "docs" / "product"
    features: list[dict[str, Any]] = []
    if not product.exists():
        return features
    for state in sorted(product.glob("FEAT-*/state.yaml")):
        try:
            data = yaml.safe_load(state.read_text()) or {}
        except yaml.YAMLError:
            continue
        features.append(
            {
                "feature_id": data.get("feature_id"),
                "current_phase": data.get("current_phase"),
                "current_phase_name": data.get("current_phase_name"),
                "path": _rel(state),
            }
        )
    return features


def _collect_checksums(root: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for rel in _KEY_FILES:
        path = root / rel
        if path.exists():
            checksums[rel] = f"sha256:{_sha256_short(path)}"
    return checksums


def build_context_graph(root: Path = ROOT, *, include_timestamp: bool = True) -> dict[str, Any]:
    """Build the context graph dict from current repository state."""
    version = ""
    vt = root / "version.txt"
    if vt.exists():
        version = vt.read_text().strip()

    spec_to_impl, adr_to_impl = _build_reference_maps(root)

    graph: dict[str, Any] = {
        "schema_version": "context_graph_v1",
        "version": version,
        "specs": _collect_specs(root, spec_to_impl),
        "adrs": _collect_adrs(root, adr_to_impl),
        "skills": _collect_skills(root),
        "services": _collect_services(root),
        "tools": _collect_tools(root),
        "features": _collect_features(root),
        "checksums": _collect_checksums(root),
    }
    if include_timestamp:
        graph["generated_at"] = datetime.now(UTC).isoformat()
    return graph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the agent context graph.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the on-disk graph differs from freshly generated content.",
    )
    args = parser.parse_args(argv)

    graph = build_context_graph()
    # Compare ignoring the timestamp so --check is stable.
    comparable = {k: v for k, v in graph.items() if k != "generated_at"}
    payload = json.dumps(graph, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not args.output.exists():
            print(f"::error::{args.output} is missing — run `make gen-context-graph`.")
            return 1
        existing = json.loads(args.output.read_text())
        existing_comparable = {k: v for k, v in existing.items() if k != "generated_at"}
        if existing_comparable != comparable:
            print(f"::error::{args.output} is stale — run `make gen-context-graph`.")
            return 1
        print(f"{args.output} is up to date.")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload)
    size_kb = len(payload.encode()) / 1024
    print(f"Wrote {args.output} ({size_kb:.1f} KB)")
    if size_kb > 50:
        print(f"::warning::context graph is {size_kb:.1f} KB (> 50 KB bootstrap target)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
