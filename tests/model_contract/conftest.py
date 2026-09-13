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
    """Primary model under test — the code default unless CONTRACT_MODEL_ID overrides it."""
    from src.shared.config import LLM_MODEL_DEFAULT

    return os.environ.get("CONTRACT_MODEL_ID", LLM_MODEL_DEFAULT)


@pytest.fixture(scope="session")
def anthropic_client():  # type: ignore[return]
    """Real Anthropic client — only constructed when API key is present."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    import anthropic

    return anthropic.Anthropic(api_key=api_key)


def response_text(response: object) -> str:
    """Concatenate the text blocks of a Messages response.

    Claude 5 responses can start with a thinking block, so ``content[0].text`` raised
    ``AttributeError`` (W14-T3 contract review, ADR-0051 §"positive change").
    """
    parts = [
        getattr(b, "text", "")
        for b in getattr(response, "content", [])
        if getattr(b, "type", "") == "text"
    ]
    return "".join(parts)


def first_json_object(text: str) -> dict:
    """Parse the first JSON object in a response that may carry a fence or trailing prose."""
    import json

    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start = cleaned.find("{")
    if start < 0:
        raise json.JSONDecodeError("no JSON object", cleaned, 0)
    depth = 0
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start : i + 1])
    raise json.JSONDecodeError("unterminated JSON object", cleaned, start)
