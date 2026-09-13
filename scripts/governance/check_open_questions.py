"""Open-questions governance gate (W11-T5, issue #350).

`specs/SPEC-TEMPLATE.md` §15 says open questions are "resolved at a HITL gate rather than
assumed", yet nothing stopped a spec from reaching ``status: approved`` with unresolved items —
the Seven-Axis Review (2026-09-12) found SPEC-API-001 approved with three. This gate closes that:

  For every ``specs/**/*.md`` whose frontmatter ``status`` is ``approved`` or ``implemented``,
  every list item in its *Open Questions* section must be resolved, i.e. carry one of the
  resolution markers (``resolved``, ``decided``, ``deferred``, ``superseded``, ``closed``,
  ``n/a``, case-insensitive) **and** a traceable reference (``ADR-NNNN``, ``RFC-NNNN``, ``#NNN``,
  ``SPEC-XXX-NNN``, ``Wnn-Tn``, a ``§`` section or the literal ``example``). A section that is
  empty or says ``None`` passes. Specs in ``draft`` / ``in-review`` are not checked — that is where
  questions belong.

Wired into DoR (`docs/process/DEFINITION_OF_READY.md`) and the Phase 4 exit criteria
(`docs/process/gates/phase-gates.yaml`); report-mode in `ci.yml` during ADR-0070 burn-in.

Exit codes: 0 = clean, 1 = at least one approved/implemented spec with an open question.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS = REPO_ROOT / "specs"

GATED_STATUSES = {"approved", "implemented"}
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_STATUS_RE = re.compile(r"^status:\s*([A-Za-z-]+)", re.M)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(?:\d+(?:\.\d+)*\.?\s*)?(.*?)\s*$", re.M)
_OQ_TITLE_RE = re.compile(r"open questions", re.I)
_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+(.*)$")
_RESOLVED_RE = re.compile(
    r"(?<![A-Za-z])(resolved|decided|deferred|superseded|closed|n/?a)(?![A-Za-z])", re.I
)
_REF_RE = re.compile(
    r"(ADR-\d{4}|RFC-\d{4}|#\d+|SPEC-[A-Z]{2,6}-\d{3}|W\d{2}-T\d+|§\s*\d|\bexample\b)", re.I
)
_NONE_RE = re.compile(r"^\s*(none|n/a|no open questions)\.?\s*$", re.I)


@dataclass
class Finding:
    spec: str
    status: str
    item: str


@dataclass
class Report:
    checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    unchecked: list[str] = field(default_factory=list)  # gated specs with no section at all

    @property
    def ok(self) -> bool:
        return not self.findings


# --------------------------------------------------------------------------- parsing


def spec_status(text: str) -> str | None:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    s = _STATUS_RE.search(m.group(1))
    return s.group(1).strip().lower() if s else None


def open_questions_section(text: str) -> str | None:
    """Body of the Open Questions section (up to the next heading of equal/higher level)."""
    heads = list(_HEADING_RE.finditer(text))
    for i, h in enumerate(heads):
        if not _OQ_TITLE_RE.search(h.group(2)):
            continue
        level = len(h.group(1))
        end = len(text)
        for nxt in heads[i + 1 :]:
            if len(nxt.group(1)) <= level:
                end = nxt.start()
                break
        body = text[h.end() : end]
        return re.sub(r"<!--.*?-->", "", body, flags=re.S)
    return None


def _items(body: str) -> list[str]:
    """Top-level list items, each joined with its continuation lines."""
    items: list[str] = []
    for line in body.splitlines():
        m = _ITEM_RE.match(line)
        if m and not line.startswith((" " * 3, "\t")):
            items.append(m.group(1).strip())
        elif items and line.strip() and not line.lstrip().startswith(">"):
            items[-1] += " " + line.strip()
    return items


def unresolved_items(body: str) -> list[str]:
    if _NONE_RE.match(body.strip() or "none"):
        return []
    return [it for it in _items(body) if not (_RESOLVED_RE.search(it) and _REF_RE.search(it))]


# --------------------------------------------------------------------------- core


def evaluate(specs: dict[str, str]) -> Report:
    """``specs`` maps a display path to file text. Pure and offline."""
    rep = Report()
    for path, text in sorted(specs.items()):
        status = spec_status(text)
        if status not in GATED_STATUSES:
            continue
        rep.checked += 1
        body = open_questions_section(text)
        if body is None:
            rep.unchecked.append(path)
            continue
        for item in unresolved_items(body):
            rep.findings.append(Finding(path, status or "?", item[:140]))
    return rep


def render(rep: Report) -> str:
    out = [f"Open-questions gate (W11-T5): {rep.checked} approved/implemented spec(s) checked"]
    out += [f"  note: {p} has no Open Questions section (nothing to check)" for p in rep.unchecked]
    for f in rep.findings:
        out.append(
            f"::error file={f.spec}::open question in a `{f.status}` spec — resolve it (mark "
            f"resolved/decided/deferred + ADR/RFC/#issue reference) or set status: in-review: "
            f"{f.item}"
        )
    out.append("RESULT: PASS" if rep.ok else f"RESULT: FAIL ({len(rep.findings)} open question(s))")
    return "\n".join(out)


def load_specs(root: Path = SPECS) -> dict[str, str]:
    return {
        str(p.relative_to(REPO_ROOT)): p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(root.rglob("*.md"))
        if p.name != "SPEC-TEMPLATE.md"
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Open-questions governance gate (W11-T5).")
    ap.add_argument("--specs", default=str(SPECS), help="spec tree to scan")
    args = ap.parse_args(argv)
    rep = evaluate(load_specs(Path(args.specs)))
    print(render(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
