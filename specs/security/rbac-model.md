# RBAC Model — HITL System

**Status:** Approved | **Owner:** Security Lead | **Reviewer:** AI Governance Lead, Tech Lead
**Last updated:** 2026-05-28
**ADR references:** ADR-0011 (HITL/HOTL Model), ADR-0008 (Secrets Management)
**Threat model:** `specs/security/threat-model.md` REM-001 (HITL operator impersonation)
**Implements:** `docs/adr/ADR-0023-frontend-architecture.md §4` (OIDC + role claims)

---

## Overview

This spec defines the role-based access control model for the HITL operator system. It addresses the open remediation item REM-001 from the STRIDE threat model: the `decided_by` field on HITL decisions must come from an authenticated, authorised session — not from a user-supplied string.

All role assignments are managed by the OIDC provider. The api-gateway validates the JWT `roles` claim on every protected endpoint.

---

## Roles

### `hitl:operator`

The standard role for human reviewers who process the HITL approval queue during normal operations.

**Capabilities:**

- View the HITL pending queue (`GET /v1/hitl/status`)
- View pending request details (`GET /v1/requests/{id}`)
- Submit APPROVE or REJECT decisions (`POST /v1/hitl/requests/{id}/decision`)
- View their own decision history (read-only)

**Cannot:**

- Modify risk score thresholds or feedback loop parameters
- Override an already-decided request
- View another operator's decision rationale (audit-only — see `hitl:auditor`)
- Enable or change autonomy levels

### `hitl:supervisor`

The elevated role for team leads who manage operator capacity and can intervene in edge cases.

**Capabilities — everything `hitl:operator` can do, plus:**

- Override an **expired** request (re-open and decide within a governance window)
- Bulk-reject a flood of requests under a single documented rationale (emergency drain — requires AI Governance Lead co-approval per the HITL queue backlog runbook)
- View the full pending queue including requests assigned to other operators
- Acknowledge and dismiss `HITLNoApprovals` and `HITLQueueDepthCritical` alerts via the operator UI
- View audit log entries for the current rolling 24-hour window

**Cannot:**

- Retroactively modify a completed (APPROVED or REJECTED) decision
- Change autonomy feature flags
- Access raw unmasked payloads (all displayed payloads remain PII-masked)

### `hitl:auditor`

The read-only role for compliance officers, DPO, and AI Governance reviewers.

**Capabilities:**

- View audit log entries (all decisions, all time windows, export to CSV)
- View HITL queue status and queue depth metrics
- View the operator decision history (including rationales for completed decisions)
- View the feedback loop bias history (`GET /v1/hitl/status` metrics)

**Cannot:**

- Submit any decision (read-only access to all HITL endpoints)
- Access request payloads or context summaries beyond what is in the audit log
- View API keys or internal service configuration

---

## Action Type Permission Matrix

All actions require at minimum the `hitl:operator` role. Some high-risk action types require `hitl:supervisor` or an AI Governance Lead counter-approval.

| `action_type`        | `hitl:operator`   | `hitl:supervisor` | AI Governance counter-approval |
| -------------------- | ----------------- | ----------------- | ------------------------------ |
| `read_file`          | ✅ APPROVE/REJECT | ✅                | Not required                   |
| `write_file`         | ✅ APPROVE/REJECT | ✅                | Not required                   |
| `execute_code`       | ✅ APPROVE/REJECT | ✅                | Not required                   |
| `send_notification`  | ✅ APPROVE/REJECT | ✅                | Not required                   |
| `deploy`             | ⛔ REJECT only    | ✅ APPROVE/REJECT | Required for APPROVE           |
| `database_write`     | ⛔ REJECT only    | ✅ APPROVE/REJECT | Required for APPROVE           |
| `external_api_call`  | ✅ APPROVE/REJECT | ✅                | Not required                   |
| `delete_resource`    | ⛔ REJECT only    | ✅ APPROVE/REJECT | Required for APPROVE           |
| `escalate_privilege` | ⛔ REJECT only    | ⛔ REJECT only    | Required for any APPROVE       |

**Rationale:** High-impact, hard-to-reverse actions (`deploy`, `database_write`, `delete_resource`, `escalate_privilege`) require supervisor level or above to approve. `escalate_privilege` requires AI Governance counter-approval under all circumstances — consistent with ADR-0015 governance requirements.

---

## JWT Claim Requirements

Every request to a HITL endpoint must include a valid Bearer token with the following claims:

```json
{
  "sub": "operator-uuid-v4",
  "email": "operator@example.com",
  "roles": ["hitl:operator"],
  "exp": 1748500000,
  "iat": 1748496400,
  "iss": "https://auth.example.com",
  "aud": "api-gateway"
}
```

| Claim   | Required | Validation                                                                      |
| ------- | -------- | ------------------------------------------------------------------------------- |
| `sub`   | Yes      | UUID v4; used as `approver_id` in the audit log and HITL decision               |
| `roles` | Yes      | Must contain at least one of `hitl:operator`, `hitl:supervisor`, `hitl:auditor` |
| `exp`   | Yes      | Must not be in the past (standard JWT validation)                               |
| `iss`   | Yes      | Must match `settings.oidc_issuer`                                               |
| `aud`   | Yes      | Must include `"api-gateway"`                                                    |

**`approver_id` field:** The `decided_by` / `approver_id` written to the audit log is always taken from the JWT `sub` claim — never from the request body. The `approver_id` field in `DecisionIn` is deprecated and will be removed in a future REST version (it is retained for backwards compatibility only).

---

## Enforcement Points

### api-gateway middleware (`src/api/rest/middleware/`)

```python
# Pseudocode — implementation target for Wave 8 auth
async def require_hitl_role(required_role: str, request: Request) -> str:
    token = extract_bearer_token(request)
    claims = verify_jwt(token, issuer=settings.oidc_issuer, audience="api-gateway")
    roles = claims.get("roles", [])
    if required_role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient role")
    return claims["sub"]  # approver_id

# Per-endpoint role requirements:
# GET  /v1/hitl/status                     → hitl:operator | hitl:supervisor | hitl:auditor
# POST /v1/hitl/requests/{id}/decision     → hitl:operator | hitl:supervisor
# POST /v1/hitl/requests/{id}/decision (deploy / delete_resource / escalate_privilege)
#                                          → hitl:supervisor (+ AI Governance for escalate)
```

### Audit log (`src/guardrails/audit_logger.py`)

The `approver_id` field on every `AuditEvent` must be the JWT `sub` claim, not a user-supplied value. This is enforced by the middleware extracting `sub` and passing it to the gateway — the `DecisionIn.approver_id` field is not forwarded to the audit logger.

### Feature flags (`src/shared/feature_flags.py`)

Feature flag evaluation (autonomy level) is not access-controlled by this RBAC model — it is controlled by ADR-0015 governance sign-off through the CI/CD pipeline (`infrastructure/feature-flags/`). Operators cannot modify feature flags via the HITL UI.

---

## Implementation Status

| Component                        | Status      | Notes                                                                           |
| -------------------------------- | ----------- | ------------------------------------------------------------------------------- |
| OIDC JWT middleware              | ⚠️ Deferred | Placeholder in `src/api/rest/middleware/`; required before production (REM-001) |
| Role claim extraction            | ⚠️ Deferred | `approver_id` currently from request body; must move to JWT `sub`               |
| Action type gating               | ⚠️ Deferred | `hitl_gateway.py` to check `action_type` against caller's role                  |
| Audit log `approver_id` from JWT | ⚠️ Deferred | Currently accepts caller-supplied value                                         |
| Frontend role-based UI gating    | ⚠️ Deferred | Role claims from OIDC to control visible actions                                |

All deferred items are blocked on the OIDC provider selection (project-specific, per ADR-0023 §4). This spec defines the target state; teams adopting the template must implement the middleware before any production deployment.

---

## Privilege Escalation Prevention

1. **No self-assignment of roles** — role claims are issued by the OIDC provider only; users cannot modify their own JWT claims.
2. **No role elevation via the API** — no endpoint accepts a role parameter; role is read only from the verified JWT.
3. **Immutable audit trail** — every HITL decision records the `approver_id` from the JWT `sub` at the time of the decision. Past decisions cannot be re-attributed.
4. **Session expiry** — JWT `exp` is validated on every request; there is no session refresh mechanism in the api-gateway. Short token lifetimes (≤ 1 hour) are recommended.
5. **`escalate_privilege` double-approval** — the AI Governance Lead approval is recorded as a second HITL decision with `action_type=escalate_privilege_governance_ack`; both decisions appear in the audit log.
