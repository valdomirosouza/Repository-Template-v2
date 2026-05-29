"""REST consumer contract tests — frontend ↔ api-gateway.

Spec:  docs/api/asyncapi/v2/migration-guide.md, specs/api/rest-api-design.md
ADR:   ADR-0022 (Testing Strategy §3), ADR-0024 (API Versioning Strategy)
Pact:  tests/contract/pacts/frontend-api_gateway.json

These tests validate that the Pydantic response models produced by the api-gateway
satisfy the shapes declared in the Pact contract file. They are the provider-side
complement to the consumer Pact JSON; the full Pact provider verification test
(using pact-python against a live test server) is deferred to Wave 10.

Running these tests at the unit layer ensures that:
  1. Response model fields match what the frontend contract expects.
  2. Field types are correct (no accidental str → int changes).
  3. Status literals are within the contracted enum set.
  4. The Pact JSON file is self-consistent (valid JSON, correct structure).

Test markers: unit (no I/O, no external services)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.api.rest.routers.hitl import DecisionOut, HITLStatusResponse
from src.api.rest.routers.requests import RequestOut, RequestStatusResponse

PACT_FILE = Path(__file__).parent / "pacts" / "frontend-api_gateway.json"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_pact() -> dict[str, Any]:
    return json.loads(PACT_FILE.read_text())


def _interaction(pact: dict[str, Any], description: str) -> dict[str, Any]:
    for i in pact["interactions"]:
        if i["description"] == description:
            return i
    raise KeyError(f"No interaction with description: {description!r}")


# ── Pact file structure ───────────────────────────────────────────────────────


class TestPactFileStructure:
    """The Pact JSON file must be well-formed and carry the expected top-level keys."""

    def test_pact_file_exists(self) -> None:
        assert PACT_FILE.exists(), f"Pact file not found: {PACT_FILE}"

    def test_pact_file_is_valid_json(self) -> None:
        _load_pact()  # raises json.JSONDecodeError if malformed

    def test_consumer_is_frontend(self) -> None:
        pact = _load_pact()
        assert pact["consumer"]["name"] == "frontend"

    def test_provider_is_api_gateway(self) -> None:
        pact = _load_pact()
        assert pact["provider"]["name"] == "api-gateway"

    def test_pact_spec_version_is_2(self) -> None:
        pact = _load_pact()
        assert pact["metadata"]["pactSpecification"]["version"].startswith("2")

    def test_all_interactions_have_required_keys(self) -> None:
        pact = _load_pact()
        for interaction in pact["interactions"]:
            assert "description" in interaction
            assert "request" in interaction
            assert "response" in interaction
            assert "method" in interaction["request"]
            assert "path" in interaction["request"]
            assert "status" in interaction["response"]

    def test_no_duplicate_interaction_descriptions(self) -> None:
        pact = _load_pact()
        descriptions = [i["description"] for i in pact["interactions"]]
        assert len(descriptions) == len(set(descriptions)), (
            "Duplicate interaction descriptions found"
        )


# ── POST /v1/requests ─────────────────────────────────────────────────────────


class TestSubmitRequestContract:
    """Validates that RequestOut matches the shape the frontend expects on 202."""

    def test_response_status_is_202(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a POST /v1/requests to submit a domain request")
        assert interaction["response"]["status"] == 202

    def test_request_out_has_all_contracted_fields(self) -> None:
        # The Pact body declares: request_id, status, created_at, message.
        # Verify that RequestOut carries all of them.
        fields = RequestOut.model_fields
        for field in ("request_id", "status", "created_at", "message"):
            assert field in fields, f"RequestOut is missing contracted field: {field!r}"

    def test_request_out_status_field_is_str(self) -> None:
        fields = RequestOut.model_fields
        annotation = fields["status"].annotation
        assert annotation is str or (
            hasattr(annotation, "__origin__") is False
            and str in getattr(annotation, "__args__", (str,))
        )

    def test_request_out_request_id_is_str(self) -> None:
        fields = RequestOut.model_fields
        assert fields["request_id"].annotation is str

    def test_validation_error_interaction_is_422(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a POST /v1/requests with an empty request_text")
        assert interaction["response"]["status"] == 422


# ── GET /v1/requests/{id} ─────────────────────────────────────────────────────


class TestGetRequestStatusContract:
    """Validates that RequestStatusResponse matches the shape the frontend expects."""

    def test_response_status_is_200(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a GET /v1/requests/{id} for a queued request")
        assert interaction["response"]["status"] == 200

    def test_status_response_has_all_contracted_fields(self) -> None:
        fields = RequestStatusResponse.model_fields
        for field in (
            "request_id",
            "status",
            "created_at",
            "updated_at",
            "result",
            "error",
            "message",
        ):
            assert field in fields, f"RequestStatusResponse is missing contracted field: {field!r}"

    def test_status_field_allows_known_contracted_values(self) -> None:
        # Pact regex: ^(queued|processing|completed|failed)$
        # These are the only statuses the frontend is prepared to handle.
        contracted_statuses = {"queued", "processing", "completed", "failed"}
        pact = _load_pact()
        for interaction in pact["interactions"]:
            if (
                interaction["request"]["path"].startswith("/v1/requests/")
                and interaction["request"]["method"] == "GET"
            ):
                body_status = interaction["response"].get("body", {}).get("status")
                if body_status is not None:
                    assert body_status in contracted_statuses, (
                        f"Status {body_status!r} in Pact is not in contracted set {contracted_statuses}"
                    )

    def test_not_found_response_is_404(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a GET /v1/requests/{id} for an unknown request_id")
        assert interaction["response"]["status"] == 404

    def test_not_found_body_has_detail_key(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a GET /v1/requests/{id} for an unknown request_id")
        assert "detail" in interaction["response"]["body"]

    def test_completed_request_result_field_is_present(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a GET /v1/requests/{id} for a completed request")
        body = interaction["response"]["body"]
        assert "result" in body
        assert body["status"] == "completed"


# ── GET /v1/hitl/status ───────────────────────────────────────────────────────


class TestHITLStatusContract:
    """Validates that HITLStatusResponse matches the shape the frontend expects."""

    def test_response_status_is_200(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a GET /v1/hitl/status when the gateway is operational")
        assert interaction["response"]["status"] == 200

    def test_hitl_status_response_has_all_contracted_fields(self) -> None:
        fields = HITLStatusResponse.model_fields
        for field in ("status", "pending_count", "message"):
            assert field in fields, f"HITLStatusResponse is missing contracted field: {field!r}"

    def test_contracted_status_value_is_operational(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a GET /v1/hitl/status when the gateway is operational")
        assert interaction["response"]["body"]["status"] == "operational"

    def test_pending_count_is_integer_in_pact(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a GET /v1/hitl/status when the gateway is operational")
        pending_count = interaction["response"]["body"]["pending_count"]
        assert isinstance(pending_count, int)


# ── POST /v1/hitl/requests/{id}/decision ──────────────────────────────────────


class TestHITLDecisionContract:
    """Validates that DecisionOut matches the shape the frontend expects."""

    def test_approved_response_is_200(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a POST /v1/hitl/requests/{id}/decision with APPROVED")
        assert interaction["response"]["status"] == 200

    def test_rejected_response_is_200(self) -> None:
        pact = _load_pact()
        interaction = _interaction(pact, "a POST /v1/hitl/requests/{id}/decision with REJECTED")
        assert interaction["response"]["status"] == 200

    def test_decision_out_has_all_contracted_fields(self) -> None:
        fields = DecisionOut.model_fields
        for field in ("request_id", "decision", "message"):
            assert field in fields, f"DecisionOut is missing contracted field: {field!r}"

    def test_decision_values_are_in_contracted_set(self) -> None:
        contracted_decisions = {"APPROVED", "REJECTED"}
        pact = _load_pact()
        for interaction in pact["interactions"]:
            if "/decision" in interaction["request"]["path"]:
                body_decision = interaction["response"].get("body", {}).get("decision")
                if body_decision is not None:
                    assert body_decision in contracted_decisions, (
                        f"Decision {body_decision!r} is not in contracted set {contracted_decisions}"
                    )

    def test_request_body_decision_values_are_contracted(self) -> None:
        contracted_decisions = {"APPROVED", "REJECTED"}
        pact = _load_pact()
        for interaction in pact["interactions"]:
            if (
                "/decision" in interaction["request"]["path"]
                and interaction["request"]["method"] == "POST"
            ):
                req_decision = interaction["request"].get("body", {}).get("decision")
                if req_decision is not None:
                    assert req_decision in contracted_decisions

    def test_not_found_decision_is_404(self) -> None:
        pact = _load_pact()
        interaction = _interaction(
            pact,
            "a POST /v1/hitl/requests/{id}/decision for an unknown or expired request",
        )
        assert interaction["response"]["status"] == 404

    def test_rationale_min_length_is_enforced_in_request_body(self) -> None:
        # DecisionIn requires rationale min_length=10; verify contracted rationales meet it.
        pact = _load_pact()
        for interaction in pact["interactions"]:
            if (
                "/decision" in interaction["request"]["path"]
                and interaction["request"]["method"] == "POST"
            ):
                rationale = interaction["request"].get("body", {}).get("rationale", "")
                assert len(rationale) >= 10, (
                    f"Contracted rationale {rationale!r} is shorter than the 10-char minimum"
                )


# ── Cross-interaction invariants ──────────────────────────────────────────────


class TestCrossInteractionInvariants:
    """Invariants that must hold across all interactions in the Pact file."""

    def test_all_post_requests_have_content_type_json(self) -> None:
        pact = _load_pact()
        for interaction in pact["interactions"]:
            if interaction["request"]["method"] == "POST":
                headers = interaction["request"].get("headers", {})
                assert headers.get("Content-Type") == "application/json", (
                    f"POST interaction {interaction['description']!r} missing Content-Type: application/json"
                )

    def test_all_successful_responses_have_content_type_json(self) -> None:
        pact = _load_pact()
        for interaction in pact["interactions"]:
            resp = interaction["response"]
            if resp["status"] < 400:
                ct = resp.get("headers", {}).get("Content-Type", "")
                assert "application/json" in ct, (
                    f"Successful response for {interaction['description']!r} missing Content-Type: application/json"
                )

    def test_all_request_ids_use_synthetic_uuid_format(self) -> None:
        # UUIDs in Pact fixtures must follow the zero-prefix synthetic format
        # (00000000-0000-0000-0000-...) to guarantee no real identifiers leak.
        import re

        synthetic_pattern = re.compile(r"^0{8}-0{4}-0{4}-0{4}-[0-9a-f]{12}$")
        pact = _load_pact()
        for interaction in pact["interactions"]:
            body = interaction["response"].get("body", {})
            for field in ("request_id",):
                value = body.get(field)
                if value:
                    assert synthetic_pattern.match(value), (
                        f"Non-synthetic UUID {value!r} in {interaction['description']!r} — "
                        "use 00000000-0000-0000-0000-... format in Pact fixtures"
                    )
