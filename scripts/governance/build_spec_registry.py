"""Generated spec registry and traceability gate (W13-T3, issue #368, ADR-0085).

Walks every spec's ADR-0085 frontmatter plus the ``Spec:`` docstring references in ``src/`` and
``tests/``, the ``requirement`` pytest markers, and ``services.yaml`` ``spec:`` fields, and
emits ``docs/governance/spec-registry.md`` (+ ``.json``) — the registry that
``docs/governance/traceability-matrix.md`` said was "not yet machine-linked".

Rules (errors fail the gate):

  S1  every spec (except templates/READMEs) has frontmatter with ``id``, ``kind``, ``status``
  S2  ``status`` ∈ draft | in-review | approved | implemented | superseded; ``id`` matches
      ``SPEC-<DOMAIN>-<NNN>``; (id, kind) is unique
  S3  every ``governing_adrs`` entry has a file in docs/adr/
  S4  every ``implemented_by`` / ``verified_by`` / ``related_specs`` path exists
  S5  an ``approved`` or ``implemented`` spec of kind ``spec`` (``policy`` kind — process,
      compliance, vision documents with no code counterpart — is exempt) has at least one
      ``implemented_by`` **or** a ``Spec:`` reference from ``src/`` — a binding spec that no
      code claims is either not implemented (status wrong) or untraceable
  S6  every ``Spec: specs/…`` reference in code/tests points at an existing spec
  S7  every ``services.yaml`` ``spec:`` path exists and carries frontmatter

``--write`` regenerates the registry files; ``--check`` (default) only validates and fails if
the committed registry is stale. Exit codes: 0 clean, 1 violations or stale registry.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _module_docstring(text: str) -> str:
    """Module docstring only — `Spec:` lines inside test bodies/literals must not count."""
    try:
        return ast.get_docstring(ast.parse(text)) or ""
    except SyntaxError:
        return text[:4000]


SPECS = REPO_ROOT / "specs"
ADR_DIR = REPO_ROOT / "docs" / "adr"
SERVICES = REPO_ROOT / "services.yaml"
OUT_MD = REPO_ROOT / "docs" / "governance" / "spec-registry.md"
OUT_JSON = REPO_ROOT / "docs" / "governance" / "spec-registry.json"
SKIP_NAMES = {"README.md", "SPEC-TEMPLATE.md", "automation-spec-template.md"}
STATUSES = ("draft", "in-review", "approved", "implemented", "superseded")
BINDING = {"approved", "implemented"}

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_ID_RE = re.compile(r"^SPEC-[A-Z0-9]{2,6}-\d{3}$")
_SPEC_REF = re.compile(r"Spec:\s+(specs/[A-Za-z0-9_./-]+\.md)")
_REQ_MARK = re.compile(
    r"pytest\.mark\.requirement\(\s*[\"'](SPEC-[A-Z]+-\d{3})(?:/([A-Z]+-\d+))?[\"']"
)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    specs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# --------------------------------------------------------------------------- harvest


def _frontmatter(text: str) -> dict[str, Any] | None:
    m = _FM_RE.match(text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def code_references(repo: Path) -> dict[str, dict[str, list[str]]]:
    """{spec path: {"src": [...], "tests": [...], "requirements": [...]}}."""
    out: dict[str, dict[str, list[str]]] = {}
    for bucket in ("src", "tests"):
        root = repo / bucket
        for p in sorted(root.rglob("*.py")) if root.exists() else []:
            if "__pycache__" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            rel = str(p.relative_to(repo))
            for m in _SPEC_REF.finditer(_module_docstring(text)):
                out.setdefault(m.group(1), {"src": [], "tests": [], "requirements": []})[
                    bucket
                ].append(rel)
    return out


def requirement_markers(repo: Path) -> dict[str, list[str]]:
    """{spec id: [test file (/FR-id)]} from @pytest.mark.requirement("SPEC-…[/FR-n]")."""
    out: dict[str, list[str]] = {}
    root = repo / "tests"
    for p in sorted(root.rglob("*.py")) if root.exists() else []:
        if "__pycache__" in p.parts:
            continue
        for m in _REQ_MARK.finditer(p.read_text(encoding="utf-8", errors="replace")):
            tag = str(p.relative_to(repo)) + (f" ({m.group(2)})" if m.group(2) else "")
            out.setdefault(m.group(1), []).append(tag)
    return out


# --------------------------------------------------------------------------- core


def evaluate(repo: Path = REPO_ROOT) -> Report:
    rep = Report()
    specs_dir = repo / "specs"
    adrs = {p.name[:8] for p in (repo / "docs" / "adr").glob("ADR-*.md")}
    refs = code_references(repo)
    reqs = requirement_markers(repo)
    seen: set[tuple[str, str]] = set()
    spec_paths: set[str] = set()

    for p in sorted(specs_dir.rglob("*.md")):
        if p.name in SKIP_NAMES:
            continue
        rel = str(p.relative_to(repo))
        spec_paths.add(rel)
        fm = _frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        if fm is None:
            rep.errors.append(
                f"S1 {rel}: no ADR-0085 frontmatter (run migrate_spec_frontmatter.py)"
            )
            continue
        sid, kind, status = (
            str(fm.get("id", "")),
            str(fm.get("kind", "spec")),
            str(fm.get("status", "")),
        )
        if not _ID_RE.match(sid):
            rep.errors.append(f"S2 {rel}: id '{sid}' is not SPEC-<DOMAIN>-<NNN>")
        if status not in STATUSES:
            rep.errors.append(f"S2 {rel}: status '{status}' not in {STATUSES}")
        if (sid, kind) in seen:
            rep.errors.append(f"S2 {rel}: duplicate (id, kind) = ({sid}, {kind})")
        seen.add((sid, kind))
        for adr in fm.get("governing_adrs") or []:
            if str(adr)[:8] not in adrs:
                rep.errors.append(f"S3 {rel}: governing ADR {adr} has no file in docs/adr/")
        for key in ("implemented_by", "verified_by", "related_specs"):
            for path in fm.get(key) or []:
                if not (repo / str(path)).exists():
                    rep.errors.append(f"S4 {rel}: {key} path does not exist -> {path}")
        code_refs = refs.get(rel, {"src": [], "tests": [], "requirements": []})
        impl = list(fm.get("implemented_by") or []) or code_refs["src"]
        if kind == "spec" and status in BINDING and not impl:  # `policy` kind is exempt (no code)
            rep.errors.append(
                f"S5 {rel}: status '{status}' but no implemented_by and no `Spec:` reference from src/"
            )
        rep.specs.append(
            {
                "id": sid,
                "kind": kind,
                "status": status,
                "owner": fm.get("owner"),
                "issue": fm.get("issue"),
                "path": rel,
                "governing_adrs": [str(a) for a in (fm.get("governing_adrs") or [])],
                "implemented_by": impl,
                "verified_by": list(fm.get("verified_by") or []) or code_refs["tests"],
                "requirement_tests": reqs.get(sid, []),
                "last_updated": str(fm.get("last_updated", "")),
            }
        )

    # S6 — code references point at real specs
    for target, buckets in sorted(refs.items()):
        if target not in spec_paths and not (repo / target).exists():
            for f in buckets["src"] + buckets["tests"]:
                rep.errors.append(f"S6 {f}: `Spec: {target}` does not exist")

    # S7 — services.yaml spec: fields
    services = yaml.safe_load((repo / "services.yaml").read_text(encoding="utf-8")) or {}
    for svc in services.get("services") or []:
        spec = svc.get("spec")
        if not spec:
            rep.warnings.append(f"S7 service '{svc.get('name')}' declares no spec: field")
            continue
        if not (repo / str(spec)).exists():
            rep.errors.append(f"S7 service '{svc.get('name')}' spec path does not exist -> {spec}")
        elif str(spec) not in spec_paths:
            rep.errors.append(
                f"S7 service '{svc.get('name')}' spec is not a registered spec -> {spec}"
            )
    return rep


# --------------------------------------------------------------------------- render


def render_markdown(rep: Report) -> str:
    counts: dict[str, int] = {}
    for s in rep.specs:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    lines = [
        "# Spec Registry (generated — do not edit)",
        "",
        "> Generated by `scripts/governance/build_spec_registry.py` (W13-T3, ADR-0085). Regenerate with",
        "> `make spec-registry`. CI fails if this file is stale or any S1–S7 rule is violated.",
        "",
        "| Status | Count |",
        "| --- | --- |",
        *[f"| {k} | {counts[k]} |" for k in STATUSES if k in counts],
        "",
        "| Id | Kind | Status | Owner | Issue | Spec | ADRs | Code | Tests | Req. markers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in sorted(rep.specs, key=lambda x: (x["id"], x["kind"])):
        lines.append(
            f"| {s['id']} | {s['kind']} | {s['status']} | {s['owner'] or ''} | "
            f"{('#' + str(s['issue'])) if s['issue'] else ''} | `{s['path']}` | "
            f"{', '.join(s['governing_adrs'])} | {len(s['implemented_by'])} | "
            f"{len(s['verified_by'])} | {len(s['requirement_tests'])} |"
        )
    lines += ["", "## Warnings", ""] + ([f"- {w}" for w in rep.warnings] or ["- none"]) + [""]
    return "\n".join(lines)


def render_console(rep: Report, *, stale: bool) -> str:
    out = [f"Spec registry (W13-T3): {len(rep.specs)} spec(s)"]
    out += [f"  WARN {w}" for w in rep.warnings]
    out += [f"::error::{e}" for e in rep.errors]
    if stale:
        out.append("::error::docs/governance/spec-registry.md is stale — run `make spec-registry`")
    out.append("RESULT: PASS" if rep.ok and not stale else "RESULT: FAIL")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Spec registry builder / gate (W13-T3).")
    ap.add_argument("--write", action="store_true", help="regenerate the registry files")
    args = ap.parse_args(argv)
    rep = evaluate()
    md = render_markdown(rep)
    payload = (
        json.dumps({"specs": rep.specs, "warnings": rep.warnings}, indent=2, sort_keys=True) + "\n"
    )
    stale = False
    if args.write:
        OUT_MD.write_text(md, encoding="utf-8")
        OUT_JSON.write_text(payload, encoding="utf-8")
    else:
        stale = not OUT_MD.exists() or OUT_MD.read_text(encoding="utf-8") != md
    print(render_console(rep, stale=stale))
    return 0 if rep.ok and not stale else 1


if __name__ == "__main__":
    sys.exit(main())
