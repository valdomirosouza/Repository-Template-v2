"""
Model contract test fixtures.

These tests make REAL LLM API calls (ANTHROPIC_API_KEY required).
They run only on PRs that modify docs/dependency-manifest.yaml or specs/ai/**,
via .github/workflows/ci-model-contract.yml.

Marker: @pytest.mark.model_contract
"""

import os

import pytest


# Skip the entire suite when no API key is present (e.g. normal CI runs).
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    skip = pytest.mark.skip(reason="ANTHROPIC_API_KEY not set — model contract tests skipped")
    for item in items:
        if "model_contract" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def model_id() -> str:
    """Primary model under test, sourced from dependency-manifest."""
    return os.environ.get("CONTRACT_MODEL_ID", "claude-sonnet-4-6")


@pytest.fixture(scope="session")
def anthropic_client():  # type: ignore[return]
    """Real Anthropic client — only constructed when API key is present."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    import anthropic

    return anthropic.Anthropic(api_key=api_key)
