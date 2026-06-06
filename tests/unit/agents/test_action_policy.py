"""Unit tests for action_policy.requires_mandatory_hitl.

ADR-0053 — mandatory HITL policy layer evaluated before risk scoring.
Numeric risk score cannot downgrade mandatory categories.
"""

import pytest

from src.agents.action_policy import requires_mandatory_hitl

# ---------------------------------------------------------------------------
# Exact-match mandatory actions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action_type",
    [
        "send-email",
        "send_email",
        "post-webhook",
        "post_webhook",
        "send-external-request",
        "send_external_request",
        "write-db-record",
        "write_db_record",
        "execute-code",
        "execute_code",
        "rotate-secret",
        "rotate_secret",
        "deploy",
        "rollback",
    ],
)
def test_exact_match_actions_are_mandatory_hitl(action_type):
    required, reason = requires_mandatory_hitl(action_type, {})
    assert required is True
    assert reason != ""


# ---------------------------------------------------------------------------
# Prefix-match mandatory actions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action_type",
    [
        "financial-transfer",
        "payment-capture",
        "rotate-credentials-now",
        "deploy-to-k8s",
        "broadcast-all-users",
        "delete-account-v2",
        "mass-notify-segment",
        "helm-upgrade-prod",
        "sandbox-escape-attempt",
        "exfiltrate-user-data",
    ],
)
def test_prefix_match_actions_are_mandatory_hitl(action_type):
    required, reason = requires_mandatory_hitl(action_type, {})
    assert required is True, f"Expected mandatory HITL for action '{action_type}'"
    assert reason != ""


# ---------------------------------------------------------------------------
# Production environment target
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("env", ["production", "prod"])
def test_production_target_environment_is_mandatory_hitl(env):
    required, reason = requires_mandatory_hitl("custom-db-write", {"target_environment": env})
    assert required is True
    assert "production" in reason.lower() or env in reason.lower()


def test_staging_environment_is_not_mandatory_hitl():
    required, _ = requires_mandatory_hitl("read-db-record", {"target_environment": "staging"})
    # read-db-record is not in exact list — staging is not mandatory
    assert required is False


# ---------------------------------------------------------------------------
# L1 data classification
# ---------------------------------------------------------------------------


def test_l1_data_classification_is_mandatory_hitl():
    required, reason = requires_mandatory_hitl("generate-report", {"data_classification": "L1"})
    assert required is True
    assert "L1" in reason


@pytest.mark.parametrize("cls", ["L2", "L3", "L4", "none", ""])
def test_non_l1_classification_not_mandatory_by_classification_alone(cls):
    required, _ = requires_mandatory_hitl("generate-report", {"data_classification": cls})
    # generate-report is not in any mandatory list
    assert required is False


# ---------------------------------------------------------------------------
# Bulk operation threshold
# ---------------------------------------------------------------------------


def test_bulk_operation_above_threshold_is_mandatory_hitl():
    required, reason = requires_mandatory_hitl("update-records", {"entity_count": 101})
    assert required is True
    assert "101" in reason or "bulk" in reason.lower()


def test_bulk_operation_at_threshold_is_not_mandatory():
    required, _ = requires_mandatory_hitl("update-records", {"entity_count": 100})
    assert required is False


def test_bulk_operation_below_threshold_is_not_mandatory():
    required, _ = requires_mandatory_hitl("update-records", {"entity_count": 5})
    assert required is False


# ---------------------------------------------------------------------------
# External effect + destructive operation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("operation", ["delete", "deploy", "notify"])
def test_external_effect_plus_destructive_operation_is_mandatory_hitl(operation):
    required, reason = requires_mandatory_hitl(
        "custom-action",
        {"external_effect": True, "operation": operation},
    )
    assert required is True
    assert operation in reason.lower()


def test_external_effect_plus_read_is_not_mandatory():
    required, _ = requires_mandatory_hitl(
        "custom-action",
        {"external_effect": True, "operation": "read"},
    )
    assert required is False


# ---------------------------------------------------------------------------
# Safe actions — must NOT require mandatory HITL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action_type,params",
    [
        ("read-db-record", {}),
        ("generate-report", {"data_classification": "L3"}),
        ("list-users", {}),
        ("get-config", {"target_environment": "local"}),
        ("run-tests", {}),
    ],
)
def test_safe_actions_do_not_require_mandatory_hitl(action_type, params):
    required, reason = requires_mandatory_hitl(action_type, params)
    assert required is False, (
        f"Action '{action_type}' should not require mandatory HITL, but got reason: {reason}"
    )


# ---------------------------------------------------------------------------
# Reason string is always non-empty when mandatory
# ---------------------------------------------------------------------------


def test_reason_is_always_non_empty_when_mandatory():
    required, reason = requires_mandatory_hitl("send-email", {})
    assert required is True
    assert len(reason) > 0


def test_reason_is_empty_string_when_not_mandatory():
    required, reason = requires_mandatory_hitl("read-db-record", {})
    assert required is False
    assert reason == ""
