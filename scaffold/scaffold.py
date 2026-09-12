#!/usr/bin/env python3
"""Service scaffolding script.

Copies the language-specific template into services/<name>/ (or frontend/<name>/)
and replaces the __SERVICE_NAME__ placeholder throughout all files and filenames.

Usage (via Makefile):
    python3 scaffold/scaffold.py --name my-service --lang python
    python3 scaffold/scaffold.py --name my-app --lang frontend

Direct usage:
    python3 scaffold/scaffold.py --name my-service --lang go --out services/my-service
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PLACEHOLDER = "__SERVICE_NAME__"
ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = Path(__file__).parent / "templates"
VALID_LANGS = ("python", "java", "go", "node", "frontend")


def _rel(path: Path) -> str:
    """Path relative to the repo when inside it, absolute otherwise (--out may point anywhere)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a new service from a template.")
    parser.add_argument("--name", required=True, help="Service name (kebab-case, e.g. my-service)")
    parser.add_argument("--lang", required=True, choices=VALID_LANGS, help="Language / framework")
    parser.add_argument(
        "--out", default=None, help="Output directory (default: services/<name> or frontend/<name>)"
    )
    args = parser.parse_args()

    name: str = args.name
    lang: str = args.lang

    if not name.replace("-", "").replace("_", "").isalnum():
        sys.exit(f"Error: service name '{name}' must be alphanumeric with hyphens/underscores.")

    template_dir = TEMPLATES_DIR / lang
    if not template_dir.is_dir():
        sys.exit(f"Error: no template found at {template_dir}")

    if args.out:
        dest = Path(args.out)
    elif lang == "frontend":
        dest = ROOT / "frontend" / name
    else:
        dest = ROOT / "services" / name

    if dest.exists():
        sys.exit(f"Error: destination '{dest}' already exists.")

    # ── Copy template tree ────────────────────────────────────────────────────
    shutil.copytree(template_dir, dest)

    # ── Rename files/dirs that contain the placeholder ────────────────────────
    # Walk bottom-up so renamed children don't break parent iteration.
    for path in sorted(dest.rglob("*"), reverse=True):
        if PLACEHOLDER in path.name or "__MODULE_NAME__" in path.name:
            # W15-T5: directories/files named __MODULE_NAME__ (src/__MODULE_NAME__, Java package
            # dirs) were never renamed, so a scaffolded Python service could not import itself.
            new_name = path.name.replace("__MODULE_NAME__", _to_module_name(name, lang)).replace(
                PLACEHOLDER, _to_module_name(name, lang)
            )
            path.rename(path.parent / new_name)

    # ── Replace placeholder text in all files ─────────────────────────────────
    module_name = _to_module_name(name, lang)
    for path in dest.rglob("*"):
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
                new_text = text.replace(PLACEHOLDER, name).replace("__MODULE_NAME__", module_name)
                if new_text != text:
                    path.write_text(new_text, encoding="utf-8")
            except UnicodeDecodeError:
                pass  # skip binary files

    print(f"✓ Scaffolded '{name}' ({lang}) → {_rel(dest)}")
    _print_next_steps(name, lang, dest)


def _to_module_name(name: str, lang: str) -> str:
    """Convert kebab-case service name to language-appropriate module name."""
    if lang in ("python", "node", "frontend"):
        return name.replace("-", "_")
    if lang == "go":
        return name.replace("-", "")
    if lang == "java":
        # com.yourorg.myservice
        return name.replace("-", "")
    return name


def _print_next_steps(name: str, lang: str, dest: Path) -> None:
    print("\nNext steps:")
    print(f"  1. Edit {_rel(dest)}/README.md   — purpose, owner, SLO")
    if lang == "python":
        print("  2. uv sync (or add to workspace in pyproject.toml)")
        print("  3. make test-python          — run tests")
    elif lang == "go":
        print(f"  2. cd {_rel(dest)} && go mod tidy")
        print(f"  3. make test-go SERVICE={name}")
    elif lang == "java":
        print(f"  2. cd {_rel(dest)} && mvn compile")
        print(f"  3. make test-java SERVICE={name}")
    elif lang in ("node", "frontend"):
        print(f"  2. cd {_rel(dest)} && pnpm install")
        print(f"  3. make test-frontend APP={name}")
    print("  4. Register in services.yaml and add scrape job to prometheus.yml")
    print("  5. Add entry to .github/CODEOWNERS")


if __name__ == "__main__":
    main()
