"""Schema-driven API fuzzing with schemathesis (W15-T3, issue #390).

Every operation the app serves is exercised with generated inputs derived from its own OpenAPI
schema, in-process (ASGI). Together with ``test_openapi_live_vs_documented.py`` (the live schema
equals the committed contract) this fuzzes the documented contract. Default checks: no 5xx, and
responses conform to the declared schema/status codes.

Authenticated operations (HITL, runs, governance) answer 401 to unauthenticated fuzzing, which
is a *valid documented* outcome; the point is that no input produces a server error.

Spec: SPEC-API-001…004 · ADR-0003, ADR-0076
"""

from __future__ import annotations

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis.checks import not_a_server_error

from src.api.rest.main import app

pytestmark = [pytest.mark.contract, pytest.mark.requirement("SPEC-API-001")]

schema = schemathesis.openapi.from_asgi("/openapi.json", app)


@schema.parametrize()
@settings(max_examples=15, deadline=None, suppress_health_check=list(HealthCheck))
def test_no_operation_produces_a_server_error(case: schemathesis.Case) -> None:
    response = case.call()
    if case.operation.path == "/ready":
        # No lifespan runs under from_asgi, so the readiness probe answers its *documented* 503
        # ("DB pool not initialised"). Status/schema conformance still apply; only the blanket
        # "any 5xx is a bug" check is excluded for this one probe.
        case.validate_response(response, excluded_checks=[not_a_server_error])
        return
    case.validate_response(response)
