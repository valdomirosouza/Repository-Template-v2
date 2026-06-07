"""Static validation of the Chaos Toolkit experiments under ``tests/chaos/experiments/``.

This makes ``pytest tests/chaos/`` collectable and meaningful (referenced by
``docs/process/WORKFLOW.md``, ``docs/process/DEFINITION_OF_RELEASE.md``, and the
``test-chaos`` gate in ``docs/process/gates/phase-gates.yaml``). It is a fast, offline
pre-flight check that every experiment is well-formed before a game-day actually runs
them with ``chaos run`` (see ``.github/workflows/chaos-schedule.yml``); it does NOT
inject any faults itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

EXPERIMENTS_DIR = Path(__file__).parent / "experiments"
EXPERIMENT_FILES = sorted(EXPERIMENTS_DIR.glob("*.yaml"))

# Keys required by the Chaos Toolkit experiment schema.
REQUIRED_KEYS = ("title", "description", "method", "steady-state-hypothesis")


@pytest.mark.chaos
def test_experiments_directory_is_not_empty() -> None:
    assert EXPERIMENT_FILES, f"no Chaos Toolkit experiments found in {EXPERIMENTS_DIR}"


@pytest.mark.chaos
@pytest.mark.parametrize("experiment", EXPERIMENT_FILES, ids=lambda p: p.name)
def test_experiment_is_well_formed(experiment: Path) -> None:
    doc = yaml.safe_load(experiment.read_text())

    assert isinstance(doc, dict), f"{experiment.name}: top level must be a mapping"

    missing = [key for key in REQUIRED_KEYS if key not in doc]
    assert not missing, f"{experiment.name}: missing required key(s) {missing}"

    assert isinstance(doc["title"], str) and doc["title"].strip(), (
        f"{experiment.name}: 'title' must be a non-empty string"
    )
    assert doc["description"], f"{experiment.name}: 'description' must be non-empty"
    assert isinstance(doc["method"], list) and doc["method"], (
        f"{experiment.name}: 'method' must be a non-empty list"
    )
    assert isinstance(doc["steady-state-hypothesis"], dict), (
        f"{experiment.name}: 'steady-state-hypothesis' must be a mapping"
    )
