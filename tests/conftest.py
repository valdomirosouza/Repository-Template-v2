"""Root conftest — shared fixtures available to all test modules."""

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
