"""OpenAPI drift — the live FastAPI schema vs the committed contract (W12-T7, issue #360).

The CI job named "Contract Drift Check" only parsed the YAML. This test gives it a contract:

  R1  the set of (path, method) operations is identical both ways
  R2  every response code the live app declares (except FastAPI's auto-generated 422) is
      documented; the contract may document *more* (404/401/503 the handlers raise but
      FastAPI cannot infer)
  R3  every live component schema (except FastAPI's auto ``HTTPValidationError`` /
      ``ValidationError``) exists in the contract, and every property the app marks required
      is required in the contract too (the contract may promise more — fields the server
      always serialises from defaults — never less)
  R4  the contract's ``RequestStatus`` enum equals the statuses the request store can hold

Adding a route, a response model or a status value without editing
``docs/api/openapi/v1/openapi.yaml`` fails this test.

Spec: SPEC-API-001…004 · ADR-0003, ADR-0076, ADR-0086
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.contract, pytest.mark.requirement("SPEC-API-001")]

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "api" / "openapi" / "v1" / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}
AUTO_SCHEMAS = {"HTTPValidationError", "ValidationError"}
AUTO_CODES = {"422"}


@pytest.fixture(scope="module")
def live() -> dict[str, Any]:
    from src.api.rest.main import app

    return app.openapi()


@pytest.fixture(scope="module")
def doc() -> dict[str, Any]:
    return yaml.safe_load(DOC_PATH.read_text(encoding="utf-8"))


def _ops(spec: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (path, m.upper())
        for path, ops in spec.get("paths", {}).items()
        for m in ops
        if m in METHODS
    }


def test_r1_operations_are_identical(live: dict[str, Any], doc: dict[str, Any]) -> None:
    live_ops, doc_ops = _ops(live), _ops(doc)
    assert live_ops - doc_ops == set(), (
        f"routes in the app but not documented: {sorted(live_ops - doc_ops)}"
    )
    assert doc_ops - live_ops == set(), (
        f"documented routes the app does not serve: {sorted(doc_ops - live_ops)}"
    )


def test_r2_live_response_codes_are_documented(live: dict[str, Any], doc: dict[str, Any]) -> None:
    missing: list[str] = []
    for path, method in sorted(_ops(live) & _ops(doc)):
        live_codes = set(live["paths"][path][method.lower()].get("responses", {})) - AUTO_CODES
        doc_codes = set(doc["paths"][path][method.lower()].get("responses", {}))
        for code in sorted(live_codes - doc_codes):
            missing.append(f"{method} {path} -> {code}")
    assert not missing, "response codes the app declares but the contract omits:\n  " + "\n  ".join(
        missing
    )


def test_r3_live_schemas_exist_in_contract_and_required_fields_are_promised(
    live: dict[str, Any], doc: dict[str, Any]
) -> None:
    live_schemas = {
        k: v
        for k, v in live.get("components", {}).get("schemas", {}).items()
        if k not in AUTO_SCHEMAS
    }
    doc_schemas = doc.get("components", {}).get("schemas", {})
    problems: list[str] = []
    for name, schema in sorted(live_schemas.items()):
        if name not in doc_schemas:
            problems.append(f"schema {name} is served by the app but not in the contract")
            continue
        live_req = set(schema.get("required", []))
        doc_req = set(doc_schemas[name].get("required", []))
        if not live_req <= doc_req:
            problems.append(
                f"schema {name}: app requires {sorted(live_req - doc_req)} but the contract "
                f"does not (contract required={sorted(doc_req)})"
            )
    assert not problems, "\n".join(problems)


def test_r4_request_status_enum_matches_the_store(doc: dict[str, Any]) -> None:
    enum = set(doc["components"]["schemas"]["RequestStatus"]["enum"])
    source = (REPO_ROOT / "src" / "agents" / "request_store.py").read_text(encoding="utf-8")
    m = re.search(r"status: str\s*#\s*([a-z_|]+)", source)
    assert m, "RequestState.status must list its values in the trailing comment"
    assert enum == set(m.group(1).split("|"))
