"""Dependency-manifest consistency and freshness gate (W12-T9, issue #362).

``docs/dependency-manifest.yaml`` is the AI-aware complement to the SBOM (ADR-0051): it pins
model ids, restates security-relevant dependency floors, and carries review dates. Nothing
compared it to the real sources, so it could — and did — drift: the Seven-Axis Review
(2026-09-12) found ``last_updated`` three months past its own quarterly cadence and a model
generation behind ``config.py``'s default.

Rules:

  M1  every ``python_packages[].version_constraint`` equals the constraint in ``pyproject.toml``
      for that package (the manifest restates, it must not diverge)
  M2  every ``ai_dependencies[].models[].model_id`` with a non-empty ``used_by`` appears in
      ``src/shared/config.py`` or ``.env.example`` (a model the code cannot select is not a
      dependency); and ``settings.llm_model``'s default is one of the manifest's model ids
  M3  ``last_updated`` and every ``last_contract_tested`` are within ``--max-age-days``
      (default 92 ≈ the manifest's own "quarterly" review cadence)
  M4  every ``used_by`` / ``contract_test_suite`` / ``pii_masking_enforced_by`` path exists
  M5  every locked package listed in ``python_packages`` is actually present in ``uv.lock``

Exit codes: 0 = clean, 1 = at least one violation (``::error``).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "docs" / "dependency-manifest.yaml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
UVLOCK = REPO_ROOT / "uv.lock"
CONFIG = REPO_ROOT / "src" / "shared" / "config.py"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

_DEP_RE = re.compile(r'^\s*"([A-Za-z0-9_.\-]+)(\[[^\]]*\])?([^"]*)",', re.M)
_LLM_MODEL_DEFAULT_RE = re.compile(r'^\s*llm_model:\s*str\s*=\s*"([^"]+)"', re.M)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def pyproject_constraints(text: str) -> dict[str, str]:
    """{package: constraint} from every dependency list in pyproject.toml."""
    return {m.group(1).lower(): m.group(3).strip() for m in _DEP_RE.finditer(text)}


def locked_packages(text: str) -> set[str]:
    return {m.group(1).lower() for m in re.finditer(r'^name = "([^"]+)"', text, re.M)}


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def evaluate(
    *,
    manifest: dict[str, Any],
    pyproject_text: str,
    uvlock_text: str,
    config_text: str,
    env_text: str,
    today: date,
    max_age_days: int,
    repo_root: Path = REPO_ROOT,
) -> Report:
    rep = Report()
    constraints = pyproject_constraints(pyproject_text)
    locked = locked_packages(uvlock_text)

    # M1 / M5 — packages
    for pkg in manifest.get("python_packages") or []:
        name = str(pkg.get("name", "")).lower()
        want = str(pkg.get("version_constraint", "")).strip()
        have = constraints.get(name)
        if have is None:
            rep.errors.append(f"M1 manifest package '{name}' is not declared in pyproject.toml")
        elif have != want:
            rep.errors.append(f"M1 manifest says {name} '{want}' but pyproject.toml says '{have}'")
        if locked and name not in locked:
            rep.errors.append(f"M5 manifest package '{name}' is not present in uv.lock")

    # M2 / M3 / M4 — models
    model_ids: set[str] = set()
    for dep in manifest.get("ai_dependencies") or []:
        for model in dep.get("models") or []:
            mid = str(model.get("model_id", ""))
            model_ids.add(mid)
            used_by = model.get("used_by") or []
            if used_by and mid not in config_text and mid not in env_text:
                rep.errors.append(
                    f"M2 model '{mid}' has used_by entries but appears in neither config.py "
                    "nor .env.example"
                )
            for path in [
                *used_by,
                model.get("contract_test_suite"),
                model.get("pii_masking_enforced_by"),
            ]:
                if path and not (repo_root / str(path)).exists():
                    rep.errors.append(f"M4 model '{mid}': path does not exist -> {path}")
            tested = _parse_date(model.get("last_contract_tested"))
            if tested is None:
                rep.errors.append(
                    f"M3 model '{mid}': last_contract_tested missing or not YYYY-MM-DD"
                )
            elif (today - tested).days > max_age_days:
                age = (today - tested).days
                rep.errors.append(
                    f"M3 model '{mid}': last_contract_tested {tested} is {age} days old "
                    f"(> {max_age_days}); re-run tests/model_contract/ (ADR-0051)"
                )
    m = _LLM_MODEL_DEFAULT_RE.search(config_text)
    if m and model_ids and m.group(1) not in model_ids:
        rep.errors.append(
            f"M2 settings.llm_model default '{m.group(1)}' is not a model_id in the manifest"
        )

    # M3 — manifest freshness
    updated = _parse_date(manifest.get("last_updated"))
    if updated is None:
        rep.errors.append("M3 manifest last_updated missing or not YYYY-MM-DD")
    elif (today - updated).days > max_age_days:
        rep.errors.append(
            f"M3 manifest last_updated {updated} is {(today - updated).days} days old "
            f"(> {max_age_days}); review it (quarterly cadence) and bump the date"
        )
    return rep


def render(rep: Report) -> str:
    out = ["Dependency-manifest gate (W12-T9)"]
    out += [f"::error::{e}" for e in rep.errors]
    out.append("RESULT: PASS" if rep.ok else f"RESULT: FAIL ({len(rep.errors)} violation(s))")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Dependency-manifest gate (W12-T9).")
    ap.add_argument("--max-age-days", type=int, default=92)
    ap.add_argument("--today", default=None, help="YYYY-MM-DD (tests / reproducibility)")
    args = ap.parse_args(argv)
    today = _parse_date(args.today) if args.today else date.today()
    assert today is not None
    rep = evaluate(
        manifest=yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {},
        pyproject_text=PYPROJECT.read_text(encoding="utf-8"),
        uvlock_text=UVLOCK.read_text(encoding="utf-8") if UVLOCK.exists() else "",
        config_text=CONFIG.read_text(encoding="utf-8"),
        env_text=ENV_EXAMPLE.read_text(encoding="utf-8") if ENV_EXAMPLE.exists() else "",
        today=today,
        max_age_days=args.max_age_days,
    )
    print(render(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
