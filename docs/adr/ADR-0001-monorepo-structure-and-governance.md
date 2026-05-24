# ADR-0001 — Monorepo Structure and Governance

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead

---

## Context

The system requires a repository strategy that can accommodate:

- Multiple services (API, agents, consumers, observability instrumentation)
- Shared governance artifacts (ADRs, specs, privacy docs, AI governance)
- Consistent CI/CD pipelines, security gates, and quality standards
- Mandatory compliance with LGPD, GDPR, EU AI Act, and OWASP LLM Top 10
- AI-specific controls (HITL/HOTL, guardrails, audit trail) applied uniformly

A polyrepo approach would scatter these concerns across many repositories,
making governance enforcement inconsistent and compliance auditing difficult.

---

## Decision

Adopt a **monorepo** with the following first-class structural pillars:

1. **Spec-Driven Development (SDD)** — specs are written and approved before any
   implementation begins; every PR must reference a spec path
2. **Architecture Decision Records (ADRs)** — all significant decisions are recorded
   in `docs/adr/` and are binding on implementation
3. **Privacy-by-design** — PII masking, DPIA/RIPD, and data retention are built into
   the repository structure and CI gates, not bolted on later
4. **AI governance** — HITL/HOTL controls, guardrails, and audit logging are
   first-class components in `src/`, not optional add-ons
5. **Unified CI/CD** — a single pipeline with quality gates applies to all components;
   no per-service pipeline exceptions

---

## Consequences

### Positive

- Single source of truth for all code, specs, ADRs, runbooks, and compliance artifacts
- Shared CI/CD pipeline enforces consistent quality and security gates across all services
- Guardrails, observability instrumentation, and governance docs are co-located with
  the code they govern — reducing drift
- Compliance audits can be performed against a single repository

### Negative / Trade-offs

- Larger repository clone size as the system grows
- Requires discipline to avoid unintended coupling between services
- CI pipeline runs affect all components; a flaky test in one service blocks all merges
  (mitigated by targeted test selection per changed path)

---

## Alternatives Considered

**Polyrepo with shared packages (npm / PyPI)**
Rejected: governance artifacts (ADRs, specs, privacy docs) would need a separate
"governance repo", creating a split between code and its governing documentation.
Security and compliance gates would need to be replicated and kept in sync across
every service repo — high operational overhead and high risk of divergence.

**Polyrepo with Git submodules for shared governance**
Rejected: submodule management is error-prone; submodule version pinning creates
a coordination burden that slows down governance updates.
