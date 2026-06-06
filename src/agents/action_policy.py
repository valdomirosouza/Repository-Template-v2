"""Mandatory HITL policy layer — evaluated BEFORE risk scoring.

Defines action categories that always require HITL regardless of risk score,
autonomy level, or numeric threshold. This is a deterministic policy gate,
not a probabilistic score gate.

Numeric risk cannot downgrade mandatory HITL. The policy reason is recorded
in audit metadata so reviewers can see why HITL was mandatory.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0053
"""

from __future__ import annotations

from typing import Any

# Actions that always require HITL — exact name match (normalized to lowercase, hyphens)
_MANDATORY_HITL_EXACT: frozenset[str] = frozenset(
    {
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
    }
)

# Action type prefixes that always require HITL
_MANDATORY_HITL_PREFIXES: tuple[str, ...] = (
    "exfiltrate",
    "export-data",
    "export_data",
    "financial",
    "payment",
    "transfer-fund",
    "charge",
    "refund",
    "delete-account",
    "delete_account",
    "modify-account",
    "modify_account",
    "mass-notify",
    "mass_notify",
    "broadcast",
    "rotate-secret",
    "rotate_secret",
    "rotate-credential",
    "rotate_credential",
    "drop-table",
    "drop_table",
    "truncate-table",
    "truncate_table",
    "deploy",
    "helm-upgrade",
    "helm_upgrade",
    "kubectl-apply",
    "kubectl_apply",
    "change-flag",
    "change_flag",
    "update-flag",
    "update_flag",
    "enable-autonomous",
    "disable-hitl",
    "sandbox-escape",
    "sandbox_escape",
)

# Target environments that always require HITL regardless of action type
_MANDATORY_HITL_ENVS: frozenset[str] = frozenset({"production", "prod"})

# Data classifications that always require HITL
_MANDATORY_HITL_CLASSIFICATIONS: frozenset[str] = frozenset({"L1"})

# Bulk action threshold — entity_count above this always requires HITL
_BULK_HITL_THRESHOLD: int = 100


def requires_mandatory_hitl(action_type: str, parameters: dict[str, Any]) -> tuple[bool, str]:
    """Return (is_mandatory, reason) — evaluated BEFORE risk score.

    When is_mandatory is True, numeric risk score cannot downgrade the decision
    to HOTL or autonomous execution. The reason string is recorded in the audit
    record so reviewers understand why HITL was mandatory.

    Args:
        action_type: The proposed action name (any case, any separator).
        parameters:  The action parameters dict from the agent output.

    Returns:
        (True, reason_string) if HITL is mandatory.
        (False, "") if score-based routing may proceed.
    """
    normalized = action_type.lower().strip()

    # 1. Exact match
    if normalized in _MANDATORY_HITL_EXACT:
        return True, f"action '{action_type}' is in the mandatory-HITL exact list"

    # 2. Prefix match
    for prefix in _MANDATORY_HITL_PREFIXES:
        if normalized.startswith(prefix):
            return True, f"action '{action_type}' matches mandatory-HITL prefix '{prefix}'"

    # 3. Production target environment
    target_env = str(parameters.get("target_environment", "")).lower().strip()
    if target_env in _MANDATORY_HITL_ENVS:
        return True, (
            f"action targets environment '{target_env}' — production writes always require HITL"
        )

    # 4. L1 data classification
    data_class = str(parameters.get("data_classification", "")).upper().strip()
    if data_class in _MANDATORY_HITL_CLASSIFICATIONS:
        return True, f"action involves {data_class} (highest-sensitivity) data classification"

    # 5. Bulk operations above threshold
    entity_count = parameters.get("entity_count", 0)
    try:
        count = int(entity_count)
    except (TypeError, ValueError):
        count = 0
    if count > _BULK_HITL_THRESHOLD:
        return True, (
            f"bulk action on {count} entities exceeds "
            f"mandatory-HITL threshold ({_BULK_HITL_THRESHOLD})"
        )

    # 6. External effect on production
    external_effect = parameters.get("external_effect", False)
    operation = str(parameters.get("operation", "")).lower()
    if external_effect and operation in {"delete", "deploy", "notify"}:
        return True, (f"external effect + operation '{operation}' always requires HITL")

    return False, ""
