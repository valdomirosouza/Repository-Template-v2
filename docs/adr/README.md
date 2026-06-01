# Architecture Decision Records (ADRs)

ADRs capture significant architectural decisions made during the evolution of this system.
Every decision that affects the overall structure, key dependencies, or operational
characteristics of the system must be recorded here.

ADRs are **binding** — implementation must align with accepted ADRs unless superseded
by a newer ADR. Changing an accepted decision requires filing a new ADR, not editing
the existing one.

---

## ADR Lifecycle

```
Proposed → Accepted → Deprecated → Superseded
```

| Status         | Meaning                                           |
| -------------- | ------------------------------------------------- |
| **Proposed**   | Under discussion; not yet binding                 |
| **Accepted**   | Binding; implementation must follow this decision |
| **Deprecated** | No longer recommended; kept for historical record |
| **Superseded** | Replaced by a newer ADR (link provided)           |

---

## ADR Template

```markdown
# ADR-NNNN — Title

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-NNNN
**Date:** YYYY-MM-DD
**Authors:** Name(s)

## Context

What situation or problem prompted this decision? What constraints apply?

## Decision

What was decided? State it clearly and unambiguously.

## Consequences

### Positive

What does this decision enable?

### Negative / Trade-offs

What does this decision cost or constrain?

## Alternatives Considered

What other options were evaluated and why were they rejected?
```

---

## Master Index

### Core Architecture

These ADRs apply to every project using this template, regardless of whether the AI Agents Module is enabled.

| ADR                                                       | Title                               | Status   | Date       |
| --------------------------------------------------------- | ----------------------------------- | -------- | ---------- |
| [ADR-0001](ADR-0001-monorepo-structure-and-governance.md) | Monorepo Structure and Governance   | Accepted | 2026-05-24 |
| [ADR-0002](ADR-0002-technology-stack-selection.md)        | Technology Stack Selection          | Accepted | 2026-05-24 |
| [ADR-0003](ADR-0003-async-api-strategy.md)                | Async API Strategy                  | Accepted | 2026-05-24 |
| [ADR-0004](ADR-0004-observability-stack.md)               | Observability Stack                 | Accepted | 2026-05-24 |
| [ADR-0005](ADR-0005-message-broker-selection.md)          | Message Broker Selection            | Accepted | 2026-05-24 |
| [ADR-0006](ADR-0006-deployment-strategy.md)               | Deployment Strategy                 | Accepted | 2026-05-24 |
| [ADR-0007](ADR-0007-service-mesh.md)                      | Service Mesh                        | Proposed | 2026-05-24 |
| [ADR-0008](ADR-0008-secrets-management.md)                | Secrets Management                  | Accepted | 2026-05-24 |
| [ADR-0009](ADR-0009-caching-strategy.md)                  | Caching Strategy                    | Accepted | 2026-05-24 |
| [ADR-0012](ADR-0012-pii-masking-strategy.md)              | PII Masking Strategy                | Accepted | 2026-05-24 |
| [ADR-0013](ADR-0013-data-retention-policy.md)             | Data Retention Policy               | Accepted | 2026-05-24 |
| [ADR-0015](ADR-0015-feature-flag-strategy.md)             | Feature Flag Strategy               | Accepted | 2026-05-25 |
| [ADR-0018](ADR-0018-db-encryption-at-rest.md)             | Database Encryption at Rest         | Accepted | 2026-05-28 |
| [ADR-0019](ADR-0019-redis-tls-value-encryption.md)        | Redis TLS and Value Encryption      | Accepted | 2026-05-28 |
| [ADR-0020](ADR-0020-finops-cost-allocation.md)            | FinOps: LLM Cost Allocation         | Accepted | 2026-05-28 |
| [ADR-0022](ADR-0022-testing-strategy.md)                  | Testing Strategy                    | Accepted | 2026-05-28 |
| [ADR-0023](ADR-0023-frontend-architecture.md)             | Frontend Architecture               | Accepted | 2026-05-28 |
| [ADR-0024](ADR-0024-api-versioning-strategy.md)           | API Versioning Strategy             | Accepted | 2026-05-28 |
| [ADR-0025](ADR-0025-language-selection.md)                | Language Selection for New Services | Accepted | 2026-05-24 |
| [ADR-0026](ADR-0026-sox-audit-log-immutability.md)        | SOX Audit Log Immutability          | Accepted | 2026-05-31 |
| [ADR-0027](ADR-0027-iso27001-change-management.md)        | ISO 27001 Change Management         | Accepted | 2026-05-31 |
| [ADR-0028](ADR-0028-dora-metrics.md)                      | DORA Metrics                        | Accepted | 2026-05-31 |
| [ADR-0029](ADR-0029-devsecops-pipeline-security.md)       | DevSecOps Pipeline Security         | Accepted | 2026-05-31 |
| [ADR-0030](ADR-0030-rtk-token-efficiency.md)              | RTK Token Efficiency Integration    | Accepted | 2026-05-31 |

### AI Agents Module _(opt-in)_

These ADRs are **only binding when the AI Agents Module is enabled** (i.e., `src/agents/` is present in your project).
See `docs/optional-extensions/ai-agents/README.md` for the activation checklist.

| ADR                                                    | Title                           | Status   | Date       |
| ------------------------------------------------------ | ------------------------------- | -------- | ---------- |
| [ADR-0010](ADR-0010-agent-framework-selection.md)      | Agent Framework Selection       | Accepted | 2026-05-24 |
| [ADR-0011](ADR-0011-hitl-hotl-model.md)                | HITL/HOTL Human Oversight Model | Accepted | 2026-05-24 |
| [ADR-0014](ADR-0014-multi-agent-harness-strategy.md)   | Multi-Agent Harness Strategy    | Accepted | 2026-05-24 |
| [ADR-0016](ADR-0016-agent-sandbox-execution-policy.md) | Agent Sandbox Execution Policy  | Accepted | 2026-05-25 |
| [ADR-0017](ADR-0017-agent-memory-architecture.md)      | Agent Memory Architecture       | Accepted | 2026-05-27 |
| [ADR-0021](ADR-0021-agent-communication-protocol.md)   | Agent Communication Protocol    | Accepted | 2026-05-28 |
