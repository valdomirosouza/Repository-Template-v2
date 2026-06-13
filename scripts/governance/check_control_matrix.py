#!/usr/bin/env python3
"""Validate the versioned security control matrices (ADR-0072).

Security claims are only assurance if they are *true*: a control entry that points at a deleted
file or a non-existent CI job is a false assurance (CLAUDE.md §3.6). This gate keeps the matrices
honest. For each matrix in `specs/security/*-control-matrix.yaml` it checks:

  1. **Structure** — conforms to `specs/security/schemas/control-matrix.schema.json` (validated
     structurally in pure Python; no third-party dependency).
  2. **Anti-rot** — every `implemented_by` path and every `verified_by` test path exists; every
     `verified_by` `ci:<job>` id and every `gate` name is a real CI job.
  3. **Anti-fabrication** — every `status: n/a` entry carries a non-empty justification.

Usage:
    python3 scripts/governance/check_control_matrix.py            # all matrices, default paths
    python3 scripts/governance/check_control_matrix.py --matrix specs/security/<name>.yaml

Exit 0 = all matrices valid; exit 1 = at least one problem (use as a CI gate).
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MATRICES = "specs/security/*-control-matrix.yaml"
_DEFAULT_SCHEMA = "specs/security/schemas/control-matrix.schema.json"
_WORKFLOWS = ".github/workflows"

_ROOT_KEYS = {"standard", "version", "source", "controls"}
_ROOT_REQUIRED = {"standard", "version", "controls"}
_CTRL_KEYS = {
    "id",
    "control",
    "implemented_by",
    "verified_by",
    "gate",
    "owner",
    "status",
    "justification",
}
_CTRL_REQUIRED = {"id", "control", "implemented_by", "verified_by", "gate", "owner", "status"}
_STATUSES = {"implemented", "partial", "n/a"}
_CI_PREFIX = "ci:"


def ci_job_names(workflows_dir: Path) -> set[str]:
    """Collect the set of CI job display names (the status-check contexts) from all workflows."""
    names: set[str] = set()
    for wf in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(doc, dict):
            continue
        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_key, job in jobs.items():
            if isinstance(job, dict) and isinstance(job.get("name"), str):
                names.add(job["name"])
            else:
                names.add(str(job_key))
    return names


def _is_nonempty_str_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 1
        and all(isinstance(x, str) and x.strip() for x in value)
    )


def validate_structure(matrix: Any, rel: str, errors: list[str]) -> bool:
    """Structural validation mirroring the schema. Returns True if the structure is OK."""
    if not isinstance(matrix, dict):
        errors.append(f"{rel}: top level must be a mapping")
        return False
    ok = True
    extra = set(matrix) - _ROOT_KEYS
    if extra:
        errors.append(f"{rel}: unknown top-level key(s): {', '.join(sorted(extra))}")
        ok = False
    for key in _ROOT_REQUIRED:
        if key not in matrix:
            errors.append(f"{rel}: missing required top-level key '{key}'")
            ok = False
    for key in ("standard", "version"):
        if key in matrix and not (isinstance(matrix[key], str) and matrix[key].strip()):
            errors.append(f"{rel}: '{key}' must be a non-empty string")
            ok = False
    controls = matrix.get("controls")
    if not isinstance(controls, list) or not controls:
        errors.append(f"{rel}: 'controls' must be a non-empty list")
        return False
    for i, ctrl in enumerate(controls):
        ok = _validate_control_structure(ctrl, f"{rel}: controls[{i}]", errors) and ok
    return ok


def _validate_control_structure(ctrl: Any, where: str, errors: list[str]) -> bool:
    if not isinstance(ctrl, dict):
        errors.append(f"{where}: must be a mapping")
        return False
    ok = True
    cid = ctrl.get("id") if isinstance(ctrl.get("id"), str) else where
    extra = set(ctrl) - _CTRL_KEYS
    if extra:
        errors.append(f"{where} ({cid}): unknown key(s): {', '.join(sorted(extra))}")
        ok = False
    for key in _CTRL_REQUIRED:
        if key not in ctrl:
            errors.append(f"{where} ({cid}): missing required key '{key}'")
            ok = False
    for key in ("id", "control", "owner"):
        if key in ctrl and not (isinstance(ctrl[key], str) and ctrl[key].strip()):
            errors.append(f"{where} ({cid}): '{key}' must be a non-empty string")
            ok = False
    for key in ("implemented_by", "verified_by"):
        if key in ctrl and not _is_nonempty_str_list(ctrl[key]):
            errors.append(f"{where} ({cid}): '{key}' must be a non-empty list of strings")
            ok = False
    if "gate" in ctrl and not (
        isinstance(ctrl["gate"], list)
        and all(isinstance(x, str) and x.strip() for x in ctrl["gate"])
    ):
        errors.append(f"{where} ({cid}): 'gate' must be a list of strings")
        ok = False
    status = ctrl.get("status")
    if status not in _STATUSES:
        errors.append(f"{where} ({cid}): 'status' must be one of {sorted(_STATUSES)}")
        ok = False
    if status == "n/a":
        just = ctrl.get("justification")
        if not (isinstance(just, str) and just.strip()):
            errors.append(
                f"{where} ({cid}): status 'n/a' requires a non-empty 'justification' "
                "(anti-fabrication, CLAUDE.md §3.6)"
            )
            ok = False
    return ok


def validate_references(
    matrix: dict[str, Any], rel: str, repo_root: Path, ci_jobs: set[str], errors: list[str]
) -> None:
    """Anti-rot: implemented_by/verified_by paths exist; ci: ids and gate names are real CI jobs."""
    for ctrl in matrix.get("controls", []):
        if not isinstance(ctrl, dict):
            continue
        cid = ctrl.get("id", "?")
        for path in ctrl.get("implemented_by", []) or []:
            if not (repo_root / path).exists():
                errors.append(f"{rel} ({cid}): implemented_by path does not exist: {path}")
        for item in ctrl.get("verified_by", []) or []:
            if isinstance(item, str) and item.startswith(_CI_PREFIX):
                job = item[len(_CI_PREFIX) :].strip()
                if job not in ci_jobs:
                    errors.append(f"{rel} ({cid}): verified_by references unknown CI job: '{job}'")
            elif not (repo_root / item).exists():
                errors.append(f"{rel} ({cid}): verified_by path does not exist: {item}")
        for name in ctrl.get("gate", []) or []:
            if name not in ci_jobs:
                errors.append(f"{rel} ({cid}): gate references unknown CI job: '{name}'")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", action="append", help="matrix file(s); default: all matrices")
    ap.add_argument("--schema", default=str(_REPO_ROOT / _DEFAULT_SCHEMA))
    ap.add_argument("--workflows-dir", default=str(_REPO_ROOT / _WORKFLOWS))
    ap.add_argument("--repo-root", default=str(_REPO_ROOT))
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root)
    if not Path(args.schema).exists():
        print(f"ERROR: schema not found: {args.schema}", file=sys.stderr)
        return 1

    matrices = args.matrix or sorted(glob.glob(str(repo_root / _DEFAULT_MATRICES)))
    if not matrices:
        print(f"ERROR: no control matrices found ({_DEFAULT_MATRICES})", file=sys.stderr)
        return 1

    ci_jobs = ci_job_names(Path(args.workflows_dir))
    errors: list[str] = []
    checked = 0

    for path_str in matrices:
        path = Path(path_str)
        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            rel = path_str
        if not path.exists():
            errors.append(f"{rel}: matrix file not found")
            continue
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{rel}: YAML parse error: {exc}")
            continue
        checked += 1
        before = len(errors)
        if validate_structure(doc, rel, errors) and isinstance(doc, dict):
            validate_references(doc, rel, repo_root, ci_jobs, errors)
            if len(errors) == before:
                n = len(doc.get("controls", []))
                std, ver = doc.get("standard"), doc.get("version")
                print(f"OK  {rel}: {std} {ver} — {n} control(s) checked")

    if errors:
        print("\nControl-matrix validation FAILED (ADR-0072):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"\nAll {checked} control matrix/matrices valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
