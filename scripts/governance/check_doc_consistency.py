"""Doc-consistency governance gate (W11-T7, issue #352).

Agents ground on README.md, CLAUDE.md and CLAUDE_SESSION_INIT.md first (CLAUDE.md §3.6), so a
stale number there propagates into every generated artifact. The Seven-Axis Review (2026-09-12)
found the README claiming 51 ADRs, CLAUDE.md claiming ADR-0001-0075 and the session primer's
"most recent" index stopping at ADR-0058 while 84 ADRs existed, plus a dead ADR link in
HITL-GOVERNANCE.md that the ADR/RFC-only link check could not see.

Rules (all deterministic):

  C1  README.md            "All <N> ADRs"                      N == number of ADR files
  C2  CLAUDE.md            "ADR-0001-ADR-<HHHH>"               HHHH == highest ADR id
  C3  CLAUDE_SESSION_INIT  "ADR Quick Index (most recent)"     highest id in table == highest ADR
  C4  docs/adr/README.md   every ADR file has an index row (the existing status gate also checks
                           this; duplicated here so C1-C3 derive from a verified source)
  L1  relative Markdown links in the root Markdown files and docs/**/*.md resolve on disk
      (the ADR/RFC-only scope of check_doc_references.py is widened; ``http(s)://``, ``mailto:``,
      pure ``#anchors`` and template placeholders like ``FEAT-{id}`` / ``<name>`` are skipped)

Exit codes: 0 = clean, 1 = at least one violation (emitted as ``::error``).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_MARKDOWN = (
    "README.md",
    "CLAUDE.md",
    "CLAUDE_SESSION_INIT.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SETUP.md",
    "CUSTOMISING.md",
    "SECURITY.md",
)
_ADR_FILE_RE = re.compile(r"^ADR-(\d{4})-.+\.md$")
_README_COUNT_RE = re.compile(r"All (\d+) ADRs")
_CLAUDE_RANGE_RE = re.compile("ADR-0001[\u2013-]ADR-(\\d{4})")  # en dash or hyphen
_ADR_ID_RE = re.compile(r"ADR-(\d{4})")
_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
_SKIP_LINK_RE = re.compile(r"^(https?://|mailto:|#|tel:)")
_PLACEHOLDER_RE = re.compile(r"[{}<>]|YYYY|NNN|XXX|\$\{|^\.\.\.$")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    links_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


# --------------------------------------------------------------------------- helpers


def adr_inventory(adr_dir: Path) -> tuple[int, int, list[str]]:
    """(count, highest_id, filenames) for docs/adr/ADR-NNNN-*.md."""
    files = sorted(p.name for p in adr_dir.glob("ADR-*.md") if _ADR_FILE_RE.match(p.name))
    ids = [int(_ADR_FILE_RE.match(n).group(1)) for n in files]  # type: ignore[union-attr]
    return len(files), (max(ids) if ids else 0), files


def quick_index_max(primer_text: str) -> int | None:
    """Highest ADR id inside the 'ADR Quick Index' table of the session primer."""
    m = re.search(r"## ADR Quick Index.*?(?=\n## |\Z)", primer_text, re.S)
    if not m:
        return None
    ids = [int(x) for x in _ADR_ID_RE.findall(m.group(0))]
    return max(ids) if ids else None


def check_links(files: list[Path], repo_root: Path, rep: Report) -> None:
    for source in files:
        rel = source.relative_to(repo_root)
        for i, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for target in _LINK_RE.findall(line):
                if _SKIP_LINK_RE.match(target) or _PLACEHOLDER_RE.search(target):
                    continue
                rep.links_checked += 1
                path = target.split("#", 1)[0]
                if not path:
                    continue
                candidate = (repo_root / path) if path.startswith("/") else (source.parent / path)
                if not candidate.exists():
                    if "deprecated/" in path.replace("\\", "/"):
                        # Local-only archive (gitignored `deprecated/`, docs/adr/EXTERNAL-INPUTS.md)
                        # — absent in CI by design: a warning, never a failure.
                        rep.warnings.append(f"L1 {rel}:{i}: archived-only link -> {target}")
                        continue
                    rep.errors.append(f"L1 {rel}:{i}: dangling link -> {target}")


# --------------------------------------------------------------------------- core


def evaluate(repo_root: Path = REPO_ROOT, *, links: bool = True) -> Report:
    rep = Report()
    adr_dir = repo_root / "docs" / "adr"
    count, highest, files = adr_inventory(adr_dir)

    # C4 — index covers every file (source of truth for C1-C3)
    index = (adr_dir / "README.md").read_text(encoding="utf-8")
    for name in files:
        if name not in index:
            rep.errors.append(f"C4 docs/adr/README.md has no row for {name}")

    # C1 — README count
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    m = _README_COUNT_RE.search(readme)
    if not m:
        rep.errors.append('C1 README.md: no "All <N> ADRs" sentence found')
    elif int(m.group(1)) != count:
        rep.errors.append(f"C1 README.md says 'All {m.group(1)} ADRs' but docs/adr/ holds {count}")

    # C2 — CLAUDE.md range
    claude = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
    m = _CLAUDE_RANGE_RE.search(claude)
    if not m:
        rep.errors.append('C2 CLAUDE.md: no "ADR-0001-ADR-NNNN" range found')
    elif int(m.group(1)) != highest:
        rep.errors.append(
            f"C2 CLAUDE.md says ADR-0001-ADR-{m.group(1)} but the highest ADR is ADR-{highest:04d}"
        )

    # C3 — primer quick index is actually "most recent"
    primer = (repo_root / "CLAUDE_SESSION_INIT.md").read_text(encoding="utf-8")
    qmax = quick_index_max(primer)
    if qmax is None:
        rep.errors.append("C3 CLAUDE_SESSION_INIT.md: no ADR Quick Index table found")
    elif qmax != highest:
        rep.errors.append(
            f"C3 CLAUDE_SESSION_INIT.md quick index stops at ADR-{qmax:04d}; highest is "
            f"ADR-{highest:04d} — it is not 'most recent'"
        )

    # L1 — links
    if links:
        targets = [repo_root / n for n in ROOT_MARKDOWN if (repo_root / n).exists()]
        targets += sorted(p for p in (repo_root / "docs").rglob("*.md") if "site" not in p.parts)
        check_links(targets, repo_root, rep)
    return rep


def render(rep: Report) -> str:
    out = [f"Doc-consistency gate (W11-T7): {rep.links_checked} relative links checked"]
    out += [f"  WARN {w}" for w in rep.warnings]
    out += [f"::error::{e}" for e in rep.errors]
    out.append("RESULT: PASS" if rep.ok else f"RESULT: FAIL ({len(rep.errors)} violation(s))")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Doc-consistency governance gate (W11-T7).")
    ap.add_argument("--repo", default=str(REPO_ROOT))
    ap.add_argument("--no-links", action="store_true", help="skip the L1 link scan")
    args = ap.parse_args(argv)
    rep = evaluate(Path(args.repo), links=not args.no_links)
    print(render(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
