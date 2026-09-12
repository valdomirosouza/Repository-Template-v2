"""Backfill ADR-0085 frontmatter on every spec (W13-T2, issue #367).

Mechanical, idempotent, and conservative:

  * a spec that already has frontmatter is only *completed* (missing keys added, never
    overwritten);
  * ``id`` is allocated per domain (``SPEC-<DOMAIN>-<NNN>``), skipping ids already in use;
  * ``status`` is carried from the document's own ``**Status:**`` body line
    (``Approved``/``Accepted`` → ``approved``, otherwise ``draft``) and the origin is recorded in
    ``status_source`` — the migration never promotes a status;
  * ``owner`` from ``**Owner:**``, ``governing_adrs`` from ``ADR-NNNN`` mentions in the header
    block, ``implemented_by`` / ``verified_by`` from ``Spec: <path>`` docstring references in
    ``src/`` and ``tests/`` (skills/sdlc/spec-lifecycle.md convention).

Templates and READMEs are skipped. Run: ``python scripts/governance/migrate_spec_frontmatter.py
[--dry-run]``. Validation lives in ``build_spec_registry.py`` (the migration writes, the
registry checks).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _module_docstring(text: str) -> str:
    """Module docstring only — `Spec:` lines inside test bodies/literals must not count."""
    try:
        return ast.get_docstring(ast.parse(text)) or ""
    except SyntaxError:
        return text[:4000]


SPECS = REPO_ROOT / "specs"
SKIP_NAMES = {"README.md", "SPEC-TEMPLATE.md", "automation-spec-template.md"}

DOMAIN_CODE = {
    "ai": "AI",
    "api": "API",
    "system": "SYS",
    "privacy": "PRIV",
    "security": "SEC",
    "observability": "OBS",
    "sre": "SRE",
    "compliance": "COMP",
    "ethics": "ETH",
    "governance": "GOV",
    "k8s": "K8S",
    "sdlc": "SDLC",
    "infrastructure": "INFRA",
    "automation": "AUTO",
    "features": "FEAT",
    "deprecated": "DEP",
}
STATUS_MAP = {"approved": "approved", "accepted": "approved", "implemented": "implemented"}
STATUSES = {"draft", "in-review", "approved", "implemented", "superseded"}

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_ID_IN_FM = re.compile(r"^id:\s*(SPEC-[A-Z]+-\d{3})", re.M)
_BODY_STATUS = re.compile(r"\*\*Status:?\*\*:?\s*([A-Za-z-]+)")
_BODY_OWNER = re.compile(r"\*\*Owner:?\*\*:?\s*([^|\n]+)")
_ADR = re.compile(r"ADR-(\d{4})")
_SPEC_REF = re.compile(r"Spec:\s+(specs/[A-Za-z0-9_./-]+\.md)")
_LGS_COMPANION = re.compile(r"SPEC-([A-Z]+)-(\d{3})")


def _existing_ids() -> set[str]:
    ids: set[str] = set()
    for p in SPECS.rglob("*.md"):
        m = _FM_RE.match(p.read_text(encoding="utf-8", errors="replace"))
        if m:
            i = _ID_IN_FM.search(m.group(1))
            if i:
                ids.add(i.group(1))
    return ids


def _code_refs() -> dict[str, tuple[list[str], list[str]]]:
    """{spec path: (implemented_by, verified_by)} from Spec: docstring lines."""
    out: dict[str, tuple[list[str], list[str]]] = {}
    for root, bucket in ((REPO_ROOT / "src", 0), (REPO_ROOT / "tests", 1)):
        for p in sorted(root.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            head = _module_docstring(p.read_text(encoding="utf-8", errors="replace"))
            for m in _SPEC_REF.finditer(head):
                lists = out.setdefault(m.group(1), ([], []))
                rel = str(p.relative_to(REPO_ROOT))
                if rel not in lists[bucket]:
                    lists[bucket].append(rel)
    return out


def _yaml_list(items: list[str]) -> str:
    return "[]" if not items else "\n" + "".join(f"  - {i}\n" for i in items).rstrip("\n")


def build_frontmatter(
    rel_path: str,
    text: str,
    *,
    spec_id: str,
    kind: str,
    refs: dict[str, tuple[list[str], list[str]]],
    today: str,
) -> str:
    header = text[:1500]
    m_status = _BODY_STATUS.search(header)
    raw_status = m_status.group(1).lower() if m_status else ""
    status = STATUS_MAP.get(raw_status, "draft")
    status_source = f"body-header:{m_status.group(1)}" if m_status else "default"
    m_owner = _BODY_OWNER.search(header)
    owner = m_owner.group(1).strip() if m_owner else "unassigned"
    adrs = sorted({f"ADR-{n}" for n in _ADR.findall(header)})
    impl, tests = refs.get(rel_path, ([], []))
    return (
        "---\n"
        f"id: {spec_id}\n"
        f"kind: {kind}\n"
        f"status: {status} # draft | in-review | approved | implemented | superseded (ADR-0085)\n"
        f"status_source: {status_source} # carried by migrate_spec_frontmatter.py, never promoted\n"
        f"owner: {owner}\n"
        "issue: null # GitHub issue number that delivered/owns this spec\n"
        f"governing_adrs: {_yaml_list(adrs)}\n"
        f"implemented_by: {_yaml_list(impl)}\n"
        f"verified_by: {_yaml_list(tests)}\n"
        "related_specs: []\n"
        f"last_updated: {today}\n"
        "---\n\n"
    )


def complete_frontmatter(
    rel_path: str,
    text: str,
    m_fm: re.Match[str],
    *,
    refs: dict[str, tuple[list[str], list[str]]],
    today: str,
) -> str:
    """Add ADR-0085 keys missing from an existing (numbered-spec) frontmatter; never overwrite."""
    block = m_fm.group(1)
    present = {
        ln.split(":", 1)[0].strip() for ln in block.splitlines() if re.match(r"^[a-z_]+:", ln)
    }
    impl, tests = refs.get(rel_path, ([], []))
    additions: list[str] = []
    if "kind" not in present:
        additions.append("kind: spec")
    if "issue" not in present:
        additions.append("issue: null # GitHub issue number that delivered/owns this spec")
    if "implemented_by" not in present:
        additions.append(f"implemented_by: {_yaml_list(impl)}")
    if "verified_by" not in present:
        additions.append(f"verified_by: {_yaml_list(tests)}")
    if "last_updated" not in present:
        additions.append(f"last_updated: {today}")
    if not additions:
        return text
    new_block = block.rstrip("\n") + "\n" + "\n".join(additions)
    return text[: m_fm.start(1)] + new_block + text[m_fm.end(1) :]


def allocate_id(domain: str, stem: str, used: set[str]) -> tuple[str, str]:
    """Return (id, kind). Companion docs of an existing numbered spec share its id."""
    m = _LGS_COMPANION.search(stem)
    if m:
        base = f"SPEC-{m.group(1)}-{m.group(2)}"
        kind = "threat-model" if stem.startswith("threat-model") else "feature-spec"
        return base, kind
    code = DOMAIN_CODE.get(domain, domain.upper()[:5])
    n = 1
    while f"SPEC-{code}-{n:03d}" in used:
        n += 1
    new = f"SPEC-{code}-{n:03d}"
    used.add(new)
    return new, "spec"


def migrate(*, dry_run: bool, today: str | None = None) -> list[str]:
    today = today or date.today().isoformat()
    used = _existing_ids()
    refs = _code_refs()
    changed: list[str] = []
    for p in sorted(SPECS.rglob("*.md")):
        if p.name in SKIP_NAMES:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = str(p.relative_to(REPO_ROOT))
        m_fm = _FM_RE.match(text)
        if m_fm:
            completed = complete_frontmatter(rel, text, m_fm, refs=refs, today=today)
            if completed != text:
                changed.append(f"{rel} -> frontmatter completed")
                if not dry_run:
                    p.write_text(completed, encoding="utf-8")
            continue
        domain = p.relative_to(SPECS).parts[0] if len(p.relative_to(SPECS).parts) > 1 else "system"
        spec_id, kind = allocate_id(domain, p.stem, used)
        fm = build_frontmatter(rel, text, spec_id=spec_id, kind=kind, refs=refs, today=today)
        changed.append(f"{rel} -> {spec_id} ({kind})")
        if not dry_run:
            p.write_text(fm + text, encoding="utf-8")
    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill ADR-0085 spec frontmatter (W13-T2).")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--today", default=None)
    args = ap.parse_args(argv)
    changed = migrate(dry_run=args.dry_run, today=args.today)
    for line in changed:
        print(("[dry-run] " if args.dry_run else "") + line)
    print(
        f"{len(changed)} spec(s) {'would be' if args.dry_run else ''} migrated".replace("  ", " ")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
