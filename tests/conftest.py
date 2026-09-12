"""Root conftest — shared fixtures available to all test modules, plus the tier-marker rule.

Tier-marker rule (W11-T8, issue #353): every test carries exactly one *tier* marker and it
matches the directory it lives in (``tests/unit`` -> ``unit`` … ``tests/performance`` ->
``benchmark``). Declare it once per module: ``pytestmark = pytest.mark.<tier>``. Before this
rule 78 % of tests were unmarked, so the per-marker counts in the ADR-0065 integrity baseline
protected almost nothing.
"""

from pathlib import Path

import pytest

from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
from src.shared.llm_client import StubLLMClient


@pytest.fixture
def stub_llm() -> StubLLMClient:
    """Default stub LLM returning an empty JSON object."""
    return StubLLMClient()


@pytest.fixture
def audit_logger() -> AuditLogger:
    """AuditLogger backed by a fresh in-memory store."""
    return AuditLogger(InMemoryAuditStorage())


# ---------------------------------------------------------------------------- tier markers

TIER_BY_DIR = {
    "unit": "unit",
    "integration": "integration",
    "security": "security",
    "abuse_cases": "abuse_case",
    "chaos": "chaos",
    "model_contract": "model_contract",
    "e2e": "e2e",
    "contract": "contract",
    "performance": "benchmark",
}
TIER_MARKERS = frozenset(TIER_BY_DIR.values())
_TESTS_ROOT = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Fail collection when a test lacks its directory's tier marker or carries a second tier."""
    problems: dict[str, str] = {}
    for item in items:
        try:
            rel = Path(str(item.fspath)).resolve().relative_to(_TESTS_ROOT)
        except ValueError:
            continue
        expected = TIER_BY_DIR.get(rel.parts[0]) if rel.parts else None
        if expected is None:
            continue
        found = {m.name for m in item.iter_markers()} & TIER_MARKERS
        if found != {expected}:
            problems.setdefault(
                str(rel),
                f"has tier markers {sorted(found) or '{}'}, expected exactly {{'{expected}'}}",
            )
    if problems:
        listing = "\n".join(f"  - {k}: {v}" for k, v in sorted(problems.items()))
        raise pytest.UsageError(
            "Tier-marker rule (W11-T8): add `pytestmark = pytest.mark.<tier>` matching the "
            f"directory.\n{listing}"
        )
