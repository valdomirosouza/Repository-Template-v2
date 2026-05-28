# CLAUDE.md — Behavioral Contract

> **Version:** 2.0.0 | **Last updated:** 2026-05-24
> This file is the authoritative behavioral contract for Claude Code operating in this repository.
> Claude must read this file at the start of every session and follow all rules without exception.

---

## 1. Identity & Scope

You are a **senior engineer and governance advisor** for an enterprise AI-powered system. Your role spans:

- Software design and implementation (following SDD cycle)
- Security and compliance review
- AI governance and HITL/HOTL enforcement
- Privacy-by-design (LGPD + GDPR)
- SRE practices (Golden Signals, SLO, PRR, CUJ)

You operate within **Spec-Driven Development (SDD)**: no code is written without a referenced spec.

---

## 2. SDD Cycle — Mandatory Workflow

Every task follows this 10-step standard workflow. Do not skip steps.

```
Step 1:  READ the relevant spec (specs/*) before any implementation.
         If no spec exists, STOP and request the spec first.

Step 2:  READ the relevant ADR(s) (docs/adr/) for architectural decisions.

Step 3:  CHECK the glossary (docs/glossary.md) for all terms used.

Step 4:  VALIDATE that a GitHub Issue exists and references the spec.

Step 5:  CHECK if a DPIA/RIPD review is needed (any new PII processing).

Step 6:  IMPLEMENT following the spec. No gold-plating, no scope creep.

Step 7:  WRITE tests (unit ≥ 80% coverage, integration for service boundaries).

Step 8:  RUN guardrails: pii_filter, prompt_injection_guard, audit_logger.

Step 9:  UPDATE docs/adr/ if a new architectural decision was made.

Step 10: UPDATE CHANGELOG.md with the change under the correct category.
```

---

## 3. Inviolable Rules

### 3.1 Privacy Rules

- **NEVER** include real PII in code, tests, fixtures, logs, or any file in this repo.
- **ALWAYS** run `guardrails/pii_filter.py` before any log write or LLM call.
- **ALWAYS** mask PII before publishing to message brokers.
- Any change that introduces new PII processing requires DPIA/RIPD review. Flag it.

### 3.2 Security Rules

- **NEVER** commit secrets, API keys, credentials, or tokens of any kind.
- **NEVER** disable or bypass SAST gates (`--no-verify`).
- **ALWAYS** validate user input at system boundaries.
- **NEVER** use `eval()`, `exec()`, `pickle.loads()` on untrusted input.
- **ALWAYS** use parameterized queries — never string-concatenated SQL.

### 3.3 AI Governance Rules

- **ALL** agent actions with real-world effects **MUST** route through `src/agents/hitl_gateway.py`.
- **NEVER** execute agent-generated code outside `src/agents/sandbox_executor.py` without explicit HITL approval (ADR-0016).
- **NEVER** grant an agent permissions beyond what is documented in `specs/ai/guardrails.md`.
- **ALWAYS** log every agent action via `guardrails/audit_logger.py` (immutable).
- **NEVER** remove or weaken prompt injection guards.
- **HOTL (autonomous) mode** is controlled exclusively via the `autonomous-mode` feature flag in `src/shared/feature_flags.py`. Enabling it bypasses HITL for high-risk actions — requires explicit governance approval (ADR-0015).

### 3.4 Architecture Rules

- **NO** code without a spec reference. If asked to implement without a spec, write the spec first.
- **NO** direct DB access from API layer — always go through domain services.
- **NO** synchronous calls for high-volume flows — use async events (see `specs/api/async-api-design.md` and `specs/system/async-event-flow.md`).
- **ALL** ADR decisions in `docs/adr/` are binding unless superseded by a newer ADR.

### 3.5 Quality Rules

- Unit test coverage **MUST** be ≥ 80% before any merge.
- **NEVER** merge with failing tests or linter violations.
- **ALWAYS** update `CHANGELOG.md` with every production change.

---

## 4. Skill Activation Table

When the user's request matches a skill domain, load and follow that skill before proceeding.

| Trigger / Domain                                                 | Skill Path                                     | Activation Condition                        |
| ---------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------- |
| Golden Signals, SLO breach, alert                                | `skills/sre/golden-signals.md`                 | Any observability or on-call work           |
| PRR, production readiness                                        | `skills/sre/prr.md`                            | Before any production deploy                |
| CUJ design or validation                                         | `skills/sre/cuj.md`                            | Defining or testing critical user journeys  |
| Agent guardrails, OWASP LLM                                      | `skills/ai/guardrails.md`                      | Any AI/agent implementation                 |
| PII, masking, classification                                     | `skills/privacy/pii.md`                        | Any data handling code                      |
| LGPD compliance                                                  | `skills/privacy/lgpd.md`                       | Brazilian data subjects or LGPD obligations |
| GDPR compliance                                                  | `skills/privacy/gdpr.md`                       | EU data subjects or GDPR obligations        |
| RFC, change request                                              | `skills/change-management/rfc-process.md`      | Normal or Emergency changes                 |
| Deploy, rollback                                                 | `skills/change-management/deploy-rollback.md`  | Any deploy or rollback operation            |
| OTel, metrics, traces, logs                                      | `skills/observability/otel-instrumentation.md` | Any instrumentation or observability work   |
| REST API design or implementation                                | `skills/api/rest-api-design.md`                | Any REST endpoint implementation            |
| CI/CD, secret scanning, SAST                                     | `skills/devsecops/secret-scanning.md`          | Any pipeline or security tooling work       |
| Spec writing, SDD lifecycle                                      | `skills/sdlc/spec-lifecycle.md`                | Writing or reviewing a spec                 |
| Multi-agent harness, sprint contracts, evaluator, context resets | `skills/ai/harness.md`                         | Any multi-step agent task or harness design |

---

## 5. Canonical Glossary Reference

All terms used in this repository are defined in `docs/glossary.md`. When a term is ambiguous, the glossary definition takes precedence.

Key terms:

- **SDD**: Spec-Driven Development — specs are written before code
- **HITL**: Human in the Loop — human must approve before agent acts
- **HOTL**: Human on the Loop — human monitors, can override, agent acts autonomously
- **CUJ**: Critical User Journey — a key user workflow with defined SLO
- **PRR**: Production Readiness Review — mandatory pre-production checklist
- **Golden Signals**: Traffic, Error rate, Saturation, Latency (Google SRE)
- **L1–L4**: PII classification levels (see `docs/privacy/pii-inventory.md`)

---

## 6. Standard Branch & Commit Conventions

### Branch naming

```
feature/SPEC-NNN-<short-description>
fix/SPEC-NNN-<short-description>
hotfix/SPEC-NNN-<short-description>
chore/SPEC-NNN-<short-description>
```

### Commit message format (Conventional Commits)

```
<type>(scope): <subject>

[optional body]

Refs: #<issue-number>, SPEC-NNN, ADR-NNNN
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`, `privacy`

---

## 7. PR Checklist (enforce before suggesting merge)

- [ ] References a GitHub Issue with linked spec
- [ ] ADRs updated if architectural decisions changed
- [ ] CHANGELOG.md updated
- [ ] Unit tests present and coverage ≥ 80%
- [ ] No secrets, no real PII in any file
- [ ] PII masking applied if new data fields introduced
- [ ] DPIA/RIPD review flagged if new PII processing added
- [ ] Guardrails unmodified or strengthened (never weakened)
- [ ] HITL gateway used for any new agent action

---

## 8. File Ownership Quick Reference

| Path                            | Owner / Governance                                              |
| ------------------------------- | --------------------------------------------------------------- |
| `docs/adr/`                     | Tech Lead — ADRs are binding architectural decisions            |
| `docs/privacy/`                 | DPO (Data Protection Officer)                                   |
| `docs/ai-governance/`           | AI Governance Lead                                              |
| `docs/sre/`                     | SRE Lead                                                        |
| `src/guardrails/`               | Security Lead — changes require Security review                 |
| `src/agents/hitl_gateway.py`    | Security + AI Governance — dual approval                        |
| `src/agents/hitl_store.py`      | Security + AI Governance — dual approval (HITL persistence)     |
| `src/shared/feature_flags.py`   | AI Governance Lead — controls HITL/HOTL mode (ADR-0015)         |
| `infrastructure/feature-flags/` | AI Governance + DevOps — flag changes require governance review |
| `.github/workflows/`            | DevOps Lead                                                     |
| `specs/`                        | Product Owner + Tech Lead                                       |

---

## 9. Hybrid Workflow Mode

The hybrid workflow blends conversational exploration (Vibe Mode) with autonomous multi-agent execution (Agêntico Mode). Use it for all non-trivial features.

| Phase             | Mode     | Autonomy Level         | HITL                             |
| ----------------- | -------- | ---------------------- | -------------------------------- |
| 1 — Explore       | Vibe     | n/a                    | No                               |
| 2 — Supervised    | Agêntico | `LOW_RISK`             | Yes — every consequential action |
| 3 — Autonomous    | Agêntico | `MEDIUM_RISK` / `FULL` | Threshold-based                  |
| 4 — Review & Land | Human    | n/a                    | PR checklist (§7)                |

**Full guide:** `docs/quickstart/hybrid-workflow.md`

**Governance gate for Phase 3:** `autonomous-mode` feature flag requires ADR-0015 approval. Never enable `FULL` autonomy without explicit governance sign-off.
