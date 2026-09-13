"""Topic-contract governance gate (W11-T3, issue #348).

Three artifacts describe the Kafka topics of this repository and nothing compared them until
this gate existed: the service registry (`services.yaml`), the AsyncAPI contract
(`docs/api/asyncapi/v1/asyncapi.yaml`) and the topic literals in code (Python
``broker.publish("…")`` / consumer ``TOPIC`` constants, Java ``${KAFKA_TOPIC_X:name}`` defaults,
Go ``getEnv("KAFKA_TOPIC_X", "name")`` defaults). CLAUDE.md §0.1 states the registry and the
contract must match; the Seven-Axis Review (2026-09-12) found one name in seventeen overlapping.

Rules (errors fail the gate, warnings do not):

  E1  registry topics == AsyncAPI channels (symmetric difference must be empty)
  E2  every topic literal in code is a registered topic
  E3  per-topic lifecycle agrees: registry ``lifecycle`` vs AsyncAPI ``x-stability``
      (``planned`` <-> ``planned``, ``reference`` <-> ``reference``; ``active`` <-> stable/beta)
  E4  every service ``publishes``/``subscribes`` entry is a registered topic
  W1  an ``active`` topic with no in-tree publisher literal and no declaring service

The core (`evaluate`) is pure and offline; `scan_*` helpers gather inputs from the tree.
Exit codes: 0 = clean (warnings allowed), 1 = at least one error (emitted as ``::error::``).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "services.yaml"
ASYNCAPI = REPO_ROOT / "docs" / "api" / "asyncapi" / "v1" / "asyncapi.yaml"

LIFECYCLES = {"active", "planned", "reference"}
# AsyncAPI x-stability values accepted for each registry lifecycle.
STABILITY_FOR = {
    "active": {"stable", "beta"},
    "planned": {"planned"},
    "reference": {"reference"},
}

_TOPIC = r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+"
_PY_PATTERNS = [
    re.compile(r"\.publish\(\s*\"(" + _TOPIC + r")\"", re.S),
    re.compile(r"^\s*TOPIC\s*=\s*\"(" + _TOPIC + r")\"", re.M),
    re.compile(r"kafka_[a-z_]*topic[a-z_]*\s*:\s*str\s*=\s*\"(" + _TOPIC + r")\""),
]
_JAVA_PATTERN = re.compile(r"\$\{KAFKA_TOPIC_[A-Z0-9_]+:(" + _TOPIC + r")\}")
_GO_PATTERN = re.compile(r"getEnv\(\s*\"KAFKA_TOPIC_[A-Z0-9_]+\"\s*,\s*\"(" + _TOPIC + r")\"")


@dataclass
class Literal:
    topic: str
    where: str  # "path:line"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# --------------------------------------------------------------------------- scanning


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:  # scanning a tree outside the repo (tests)
        return str(path)


def scan_python(root: Path) -> list[Literal]:
    out: list[Literal] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in _PY_PATTERNS:
            for m in pat.finditer(text):
                out.append(Literal(m.group(1), f"{_rel(path)}:{_line_of(text, m.start())}"))
    return out


def scan_java(root: Path) -> list[Literal]:
    out: list[Literal] = []
    for path in sorted(root.rglob("application*.y*ml")):
        if "src/main" not in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _JAVA_PATTERN.finditer(text):
            out.append(Literal(m.group(1), f"{_rel(path)}:{_line_of(text, m.start())}"))
    return out


def scan_go(root: Path) -> list[Literal]:
    out: list[Literal] = []
    for path in sorted(root.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _GO_PATTERN.finditer(text):
            out.append(Literal(m.group(1), f"{_rel(path)}:{_line_of(text, m.start())}"))
    return out


def scan_code(repo: Path = REPO_ROOT) -> list[Literal]:
    lits = scan_python(repo / "src")
    services = repo / "services"
    if services.exists():
        lits += scan_java(services) + scan_go(services)
    return lits


def load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_asyncapi(path: Path = ASYNCAPI) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# --------------------------------------------------------------------------- core


def evaluate(
    *,
    registry: dict[str, Any],
    asyncapi: dict[str, Any],
    literals: list[Literal],
) -> Report:
    """Pure evaluation of the five rules. Inputs are parsed YAML dicts and scanned literals."""
    rep = Report()
    topics = registry.get("topics") or []
    reg: dict[str, str] = {}
    for t in topics:
        name = str(t.get("name", "")).strip()
        lc = str(t.get("lifecycle", "active")).strip()
        if lc not in LIFECYCLES:
            rep.errors.append(
                f"topic '{name}': unknown lifecycle '{lc}' (allowed: {sorted(LIFECYCLES)})"
            )
            lc = "active"
        reg[name] = lc
    channels: dict[str, str] = {
        str(name): str((spec or {}).get("x-stability", "stable"))
        for name, spec in (asyncapi.get("channels") or {}).items()
    }

    # E1 — registry == contract
    only_reg = sorted(set(reg) - set(channels))
    only_api = sorted(set(channels) - set(reg))
    if only_reg:
        rep.errors.append(
            "E1 topics in services.yaml but not in AsyncAPI channels: " + ", ".join(only_reg)
        )
    if only_api:
        rep.errors.append(
            "E1 AsyncAPI channels not registered in services.yaml topics: " + ", ".join(only_api)
        )

    # E2 — code literals are registered
    for lit in literals:
        if lit.topic not in reg:
            rep.errors.append(
                f"E2 code publishes/consumes unregistered topic '{lit.topic}' ({lit.where})"
            )

    # E3 — lifecycle agreement
    for name, lc in sorted(reg.items()):
        stab = channels.get(name)
        if stab is None:
            continue  # already an E1 error
        if stab not in STABILITY_FOR[lc]:
            rep.errors.append(
                f"E3 topic '{name}': services.yaml lifecycle '{lc}' vs AsyncAPI x-stability "
                f"'{stab}' (expected one of {sorted(STABILITY_FOR[lc])})"
            )

    # E4 — service declarations are registered; also collect declared publishers for W1
    declared_publishers: dict[str, list[str]] = {}
    for svc in registry.get("services") or []:
        sname = str(svc.get("name", "?"))
        for key in ("publishes", "subscribes"):
            for topic in svc.get(key) or []:
                if topic not in reg:
                    rep.errors.append(f"E4 service '{sname}' {key} unregistered topic '{topic}'")
                elif key == "publishes":
                    declared_publishers.setdefault(str(topic), []).append(sname)

    # W1 — active topic nobody publishes
    code_topics = {lit.topic for lit in literals}
    for name, lc in sorted(reg.items()):
        if lc == "active" and name not in code_topics and name not in declared_publishers:
            rep.warnings.append(
                f"W1 topic '{name}' is lifecycle 'active' but no code literal or service "
                "publishes it; set lifecycle: planned|reference or wire a publisher"
            )
    return rep


def render(rep: Report, *, n_topics: int, n_literals: int) -> str:
    out = [
        f"Topic-contract gate (W11-T3): {n_topics} registered topics, {n_literals} code literals"
    ]
    out += [f"  WARN {w}" for w in rep.warnings]
    out += [f"::error::{e}" for e in rep.errors]
    out.append("RESULT: PASS" if rep.ok else f"RESULT: FAIL ({len(rep.errors)} error(s))")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Topic-contract governance gate (W11-T3).")
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--asyncapi", default=str(ASYNCAPI))
    ap.add_argument("--repo", default=str(REPO_ROOT), help="tree to scan for topic literals")
    args = ap.parse_args(argv)
    registry = load_registry(Path(args.registry))
    asyncapi = load_asyncapi(Path(args.asyncapi))
    literals = scan_code(Path(args.repo))
    rep = evaluate(registry=registry, asyncapi=asyncapi, literals=literals)
    print(render(rep, n_topics=len(registry.get("topics") or []), n_literals=len(literals)))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
