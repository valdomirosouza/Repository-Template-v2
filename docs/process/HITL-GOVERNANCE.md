# HITL Governance — Two-Tier Architecture

> **Version:** 1.0.0 | **Last updated:** 2026-06-06
> **Owner:** Security Lead + AI Governance Lead | **Approver:** Governance Council
> **ADR:** ADR-0052 | **Source:** agentic-sdlc-open-questions-resolved.md Q2

---

## Overview

The HITL (Human in the Loop) governance model in this repository uses a **two-tier architecture** that matches the risk level of each action to the appropriate oversight mechanism.

| Tier                      | Mechanism                    | Used For                                                                  | Overhead                      |
| ------------------------- | ---------------------------- | ------------------------------------------------------------------------- | ----------------------------- |
| **Tier 1** — Spec-as-PR   | GitHub PR review             | Pre-code artefacts (discovery, NFR, spec)                                 | Low — async, reviewer-in-loop |
| **Tier 2** — Runtime HITL | `src/agents/hitl_gateway.py` | Agent actions with real-world effects (API calls, DB writes, deployments) | High — synchronous block      |

**Key principle:** Discovery and specification artefacts do NOT pass through the runtime HITL gateway. The gateway is reserved for actions — not artefacts. The PR review process is the HITL equivalent for pre-code phases.

---

## Tier 1 — Spec-as-PR Governance

### What it covers

All documents in the following paths are governed via Spec-as-PR:

| Path                                       | Artefact                      | Required Reviewers                              |
| ------------------------------------------ | ----------------------------- | ----------------------------------------------- |
| `docs/product/FEAT-{id}/discovery.md`      | Discovery Primer              | Product Owner + Tech Lead                       |
| `docs/product/FEAT-{id}/nfr.md`            | NFR document                  | Security Lead (blocking) + Tech Lead            |
| `specs/features/FEAT-{id}/feature-spec.md` | Feature specification         | Tech Lead + Security Lead (if security surface) |
| `docs/adr/ADR-{nnnn}-*.md`                 | Architectural Decision Record | Tech Lead (1 required)                          |
| `docs/process/`                            | Process documents             | Tech Lead + Governance Council                  |

### How it works

1. Agent or developer creates/updates the artefact in a branch.
2. PR opened with the artefact — title prefixed with `docs(product):` or `docs(spec):`.
3. Required reviewers are auto-assigned by CODEOWNERS.
4. Reviewers are the HITL equivalent: they may approve, request changes, or reject.
5. Only after PR merge can the artefact be used to gate the next phase.

### Agent-Disclosure Requirement

Every agent-generated document submitted via Spec-as-PR **must** include the disclosure header defined in `docs/product/README.md`. Missing disclosure headers cause the `harness/doc-check.yml` gate to fail.

---

## Tier 2 — Runtime HITL Gateway

### What it covers

All agent actions with real-world effects:

| Action Category      | Examples                                 | Default Mode                                 |
| -------------------- | ---------------------------------------- | -------------------------------------------- |
| External API calls   | Send email, call webhook, post to Slack  | HITL (block + wait)                          |
| Database writes      | INSERT, UPDATE, DELETE via service layer | HITL (block + wait)                          |
| File system writes   | Modify config files, write artefacts     | HOTL (monitor) if `LOW_RISK` flag enabled    |
| Code execution       | Run generated code                       | HITL — requires `sandbox_executor.py`        |
| Deployments          | `helm upgrade`, `kubectl apply`          | HITL — requires RFC + CAB approval           |
| Feature flag changes | Enable/disable `autonomous-mode`         | HITL — requires ADR-0015 governance sign-off |

### Autonomy Levels

Controlled exclusively by `src/shared/feature_flags.py`. Evaluated in order:

```
FULL > MEDIUM_RISK > LOW_RISK > TESTS_ONLY > READ_ONLY > NONE
```

| Level            | Actions that bypass HITL               | Governance Required            |
| ---------------- | -------------------------------------- | ------------------------------ |
| `NONE` (default) | None — all actions blocked             | —                              |
| `READ_ONLY`      | Read-only operations                   | Tech Lead                      |
| `TESTS_ONLY`     | Test execution only                    | Tech Lead                      |
| `LOW_RISK`       | Low-risk writes (config, non-PII data) | Tech Lead                      |
| `MEDIUM_RISK`    | Medium-risk actions                    | Governance Council             |
| `FULL`           | All actions — bypasses all HITL        | ADR-0015 + Governance sign-off |

### Runtime HITL Flow

```
Agent proposes action
    └─ HITLGateway.request_approval(action, context)
        ├─ autonomy_level < action.risk_level?
        │   ├─ YES → Store in HITLRedisStore (encrypted); POST /v1/hitl/{id}/decide
        │   │         Block agent execution
        │   │         Operator reviews in HITL approval UI (frontend/)
        │   │         → Approved: resume execution
        │   │         → Rejected: action cancelled; agent notified
        │   └─ NO  → Execute with audit log entry
        └─ Always: audit_logger.log(action, decision, actor)
```

---

## Enterprise Best Practices

### 1. Least-Privilege Autonomy by Default

The default autonomy level is `NONE`. Teams must explicitly opt in to higher autonomy levels through the governance process. This inverts the typical "enable everything, restrict later" pattern.

### 2. Immutable Audit Trail

Every HITL decision (approved, rejected, auto-approved) produces an immutable audit log entry via `guardrails/audit_logger.py`. Audit logs are:

- Append-only (no UPDATE or DELETE)
- Tagged with `request_id`, `agent_id`, `action_type`, `decision`, `actor`, and `timestamp`
- Retained per the SOX 7-year policy (if applicable) or minimum 90 days

### 3. Encrypted HITL Payloads

HITL request payloads stored in Redis must use `HITLRedisStore` with an `EncryptedField` (AES-256-GCM). Plaintext payloads in Redis are blocked in production by `Settings.reject_placeholder_secrets`. See ADR-0018, ADR-0019.

### 4. HOTL Monitoring Obligation

When `MEDIUM_RISK` or `FULL` autonomy is enabled (HOTL mode), human monitors are required to:

- Review the Grafana agent-actions dashboard daily
- Respond to `AGENT_ACTION_ANOMALY` alerts within the SLO MTTD target
- Record any override decisions in the audit log with rationale

---

## Reviewer Assignment by Artefact

| Artefact / Action             | Primary Reviewer   | Secondary Reviewer            | Escalation                         |
| ----------------------------- | ------------------ | ----------------------------- | ---------------------------------- |
| `discovery.md`                | Product Owner      | Tech Lead                     | Governance Council                 |
| `nfr.md`                      | Security Lead      | Tech Lead                     | CISO                               |
| `feature-spec.md`             | Tech Lead          | Security Lead                 | Governance Council                 |
| HITL runtime approval         | Operator (Tier 1)  | Tech Lead (Tier 2 escalation) | Security Lead                      |
| Autonomy level change         | AI Governance Lead | Security Lead                 | CTO                                |
| `hitl_gateway.py` code change | Security Lead      | AI Governance Lead            | Governance Council (dual approval) |

---

## Related

- `src/agents/hitl_gateway.py` — Runtime implementation
- `src/agents/hitl_store.py` — Encrypted HITL payload persistence
- `src/shared/feature_flags.py` — Autonomy level feature flags
- `docs/process/RACI.md` — Who owns each decision
- `docs/adr/ADR-0015-autonomy-levels.md` — Autonomy governance ADR
- `docs/adr/ADR-0034-agentic-escalation-protocol.md` — Escalation protocol
- `infrastructure/feature-flags/` — flagd configuration
