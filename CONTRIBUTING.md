# Contributing Guide

> **Version:** 2.0.0 | **Last updated:** 2026-05-24

Thank you for contributing. This guide describes the full contribution process for this repository, including the SDD (Spec-Driven Development) cycle, branch naming, PR process, and commit conventions.

---

## 1. Spec-Driven Development (SDD)

**No code is written without a referenced spec.** This is the most important rule in this repository.

### SDD Cycle

```
1. SPEC    → Write or identify the spec in specs/* that governs the change
2. ADR     → Check docs/adr/ for relevant architectural decisions
3. ISSUE   → Open a GitHub Issue referencing the spec
4. RFC     → File docs/change-management/rfc/RFC-NNNN-<title>.md for Normal/Emergency changes
5. BRANCH  → Create branch following naming convention below
6. CODE    → Implement against the spec — no gold-plating
7. TEST    → Write tests (unit ≥ 80%, integration for service boundaries)
8. PR      → Open PR using the template; link issue + spec + ADRs
9. REVIEW  → Minimum 1 approved reviewer; security review if guardrails touched
10. MERGE  → Squash or merge commit; CHANGELOG.md updated; branch deleted
```

---

## 2. Branch Naming

All branches must follow this pattern:

```
<type>/SPEC-NNN-<short-description>
```

| Type        | Use for                                              |
| ----------- | ---------------------------------------------------- |
| `feature/`  | New features or capabilities                         |
| `fix/`      | Bug fixes                                            |
| `hotfix/`   | Critical production fixes (Emergency change process) |
| `chore/`    | Tooling, dependencies, CI changes                    |
| `docs/`     | Documentation-only changes                           |
| `refactor/` | Refactoring with no functional change                |
| `security/` | Security fixes (may use private branch)              |

**Examples:**

```
feature/SPEC-042-hitl-approval-flow
fix/SPEC-017-pii-filter-email-regex
hotfix/SPEC-001-agent-timeout-crash
```

---

## 3. Commit Conventions

This repository uses **Conventional Commits** to drive automated changelogs and release versioning.

### Format

```
<type>(<scope>): <short subject in imperative mood>

[optional body — explain WHY, not what]

Refs: #<issue-number>[, SPEC-NNN][, ADR-NNNN][, RFC-NNNN]
```

### Types

| Type       | Triggers           | Description                           |
| ---------- | ------------------ | ------------------------------------- |
| `feat`     | Minor version bump | New feature                           |
| `fix`      | Patch version bump | Bug fix                               |
| `docs`     | No release         | Documentation only                    |
| `refactor` | No release         | Code restructure, no behaviour change |
| `test`     | No release         | Adding or updating tests              |
| `chore`    | No release         | Build, tooling, deps                  |
| `security` | Patch version bump | Security fix                          |
| `privacy`  | Patch version bump | Privacy control change                |
| `perf`     | Patch version bump | Performance improvement               |

### Breaking changes

Append `!` to type or add `BREAKING CHANGE:` footer:

```
feat(api)!: rename /v1/agents endpoint to /v1/agent-actions

BREAKING CHANGE: All callers must update to the new endpoint path.

Refs: #99, SPEC-010, ADR-0006, RFC-0007
```

---

## 4. Pull Request Process

### Before opening a PR

Run the checks for your language stack:

| Stack    | Test command                    | Lint command                    |
| -------- | ------------------------------- | ------------------------------- |
| Python   | `make test-python`              | `make lint-python`              |
| Java     | `make test-java SERVICE=<name>` | `make lint-java SERVICE=<name>` |
| Go       | `make test-go SERVICE=<name>`   | `make lint-go SERVICE=<name>`   |
| Frontend | `make test-frontend APP=<name>` | `make lint-frontend APP=<name>` |

Then confirm the full checklist:

- [ ] Tests pass locally (see table above)
- [ ] Lint passes locally (see table above)
- [ ] No secrets or real PII in any changed file
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Spec referenced in commit messages and PR description
- [ ] ADR updated or new ADR filed if architectural decision made
- [ ] `services.yaml` updated if a new service was added (see [add-new-service.md](docs/quickstart/add-new-service.md))
- [ ] `infrastructure/monitoring/prometheus/prometheus.yml` updated if a new service was added

### PR template

Use `.github/pull_request_template.md` — it is automatically populated when you open a PR.

### Required reviewers

| Change type                     | Required reviewers                 |
| ------------------------------- | ---------------------------------- |
| Standard                        | 1 approving reviewer               |
| `src/guardrails/` changes       | Security Lead (mandatory)          |
| `src/agents/hitl_gateway.py`    | Security Lead + AI Governance Lead |
| `docs/privacy/` changes         | DPO review                         |
| `docs/adr/` changes             | Tech Lead                          |
| `.github/workflows/` changes    | DevOps Lead                        |
| Infrastructure (Terraform/Helm) | DevOps Lead + Tech Lead            |

### Quality gates (all blocking)

| Gate             | Criterion                            |
| ---------------- | ------------------------------------ |
| Lint             | Zero critical rule violations        |
| Unit tests       | Coverage ≥ 80%, zero failures        |
| SAST             | Zero CRITICAL/HIGH findings          |
| Secret detection | Zero secrets detected                |
| PII scan         | No real PII in test fixtures or logs |
| Human review     | Minimum 1 approved reviewer          |

---

## 5. Change Management

### Standard changes

Minor enhancements and bug fixes follow the standard branch/PR process above.

### Normal changes

Any change that:

- Modifies system architecture
- Changes a public API contract
- Introduces or changes PII processing
- Modifies AI agent behaviour or guardrails

Requires: RFC filed at `docs/change-management/rfc/RFC-NNNN-<title>.md` and CAB review.

### Emergency changes (hotfix)

Critical production fixes that cannot wait for the standard process:

1. Notify Tech Lead and Security Lead via incident channel
2. File an RFC async (within 24h post-fix)
3. Get TL + SecOps async approval
4. Branch: `hotfix/SPEC-NNN-<description>`
5. Expedited review (minimum Tech Lead approval)
6. Post-deploy: file post-mortem within 48h

See `docs/change-management/README.md` for full process.

---

## 6. Privacy-by-Design Requirements

All contributors must adhere to these rules:

1. **No real PII in test fixtures** — use synthetic data only
2. **No PII in log statements** — run `guardrails/pii_filter.py` before every log write
3. **Flag new PII processing** — if your change introduces a new field that contains personal data, flag it in the PR description and request DPO review
4. **Do not weaken masking** — any change to `src/guardrails/pii_filter.py` must be reviewed by the Security Lead

---

## 7. Testing Requirements

| Test type         | When required                 | Location             |
| ----------------- | ----------------------------- | -------------------- |
| Unit tests        | All new functions/methods     | `tests/unit/`        |
| Integration tests | New service boundaries        | `tests/integration/` |
| Security tests    | Changes to guardrails or auth | `tests/security/`    |
| Contract tests    | Changes to public API         | `tests/contract/`    |
| Performance tests | Changes to hot paths          | `tests/performance/` |

Run the full suite: `make test`

---

## 8. Documentation Requirements

- **CHANGELOG.md** — update `[Unreleased]` section for every change
- **ADR** — file a new ADR for every significant architectural decision
- **Spec** — update the relevant spec if implementation diverges from it
- **Runbooks** — update runbooks if operational procedures change

---

## 9. Code of Conduct

All contributors are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## 10. Questions?

- Architecture questions → open a GitHub Discussion or ping the Tech Lead
- Privacy questions → contact dpo@\<org-domain\>
- Security concerns → see `SECURITY.md` for private reporting
