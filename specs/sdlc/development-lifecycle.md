# Development Lifecycle Spec

**Status:** Approved | **Owner:** Tech Lead | **Last updated:** 2026-05-28
**ADR references:** ADR-0001 (Monorepo Governance), ADR-0003 (Async API), ADR-0006 (Deployment)
**Related:** `CLAUDE.md §2` (SDD Cycle), `CLAUDE.md §6` (Branch & Commit), `harness/code-check.yml`

---

## 1. Overview

Every change follows a five-stage lifecycle: **Spec → Implement → Verify → Stage → Produce**.
No stage may be skipped. The SDD cycle in `CLAUDE.md §2` maps directly to stages 1–3.

```
Spec ──▶ Implement ──▶ Verify ──▶ Stage ──▶ Produce
  │          │            │          │          │
GitHub    feature/     CI gates   staging    canary
Issue     branch       (ci.yml)   smoke      deploy
+ spec                            tests      (cd-production.yml)
```

---

## 2. Stage 1 — Spec

**Entry condition:** A GitHub Issue exists describing the problem or feature.

**Required artefacts before any code is written:**

| Artefact                            | Location                   | Owner                       |
| ----------------------------------- | -------------------------- | --------------------------- |
| Spec file                           | `specs/<domain>/<name>.md` | Product Owner + Tech Lead   |
| Linked GitHub Issue                 | GitHub                     | Product Owner               |
| ADR (if new architectural decision) | `docs/adr/ADR-NNNN-*.md`   | Tech Lead                   |
| DPIA/RIPD review triggered          | `docs/privacy/dpia/`       | DPO — if new PII processing |

**Exit gate:** Spec is merged to `main` with Tech Lead approval. Issue references the spec path.

---

## 3. Stage 2 — Implement

**Branch naming:** `feature/SPEC-NNN-<short-description>` (see `CLAUDE.md §6`)

**Non-negotiable implementation rules:**

- All new code must reference its governing spec at the module docstring level (`Spec: specs/...`)
- No code may bypass `HITLGateway` for actions with real-world effects (AI Agents Module)
- PII masking applied at every boundary crossing (LLM, log, broker, vector store)
- No secrets committed — `detect-secrets` pre-commit hook enforces this
- DB queries use parameterized statements only — never string-concatenated SQL

**Pre-commit hooks** (`.pre-commit-config.yaml`) run automatically on every commit:
ruff lint + format, mypy strict, detect-secrets, bandit SAST.

---

## 4. Stage 3 — Verify (CI Gates)

All gates are defined in `harness/code-check.yml` and enforced by `.github/workflows/ci.yml`.
**All blocking gates must pass before a PR may be merged.**

| Gate            | Tool                                                            | Threshold                  | Blocking      |
| --------------- | --------------------------------------------------------------- | -------------------------- | ------------- |
| Lint            | ruff + mypy strict                                              | Zero violations            | Yes           |
| Unit tests      | pytest                                                          | ≥ 80% line coverage        | Yes           |
| SAST            | bandit                                                          | No MEDIUM/HIGH findings    | Yes           |
| Secret scan     | detect-secrets                                                  | No new secrets vs baseline | Yes           |
| PII leakage     | `tests/security/test_pii_leakage.py`                            | All assertions pass        | Yes           |
| Spec compliance | PR body contains `specs/` path                                  | Reference present          | No (advisory) |
| ADR index       | All linked ADR files exist                                      | Zero broken links          | Yes           |
| Contract drift  | OpenAPI + AsyncAPI parseable; `services.yaml` schema refs valid | Zero errors                | Yes           |

**PR requirements:**

- At least one approval from a `CODEOWNERS` reviewer
- All CI jobs green
- `CHANGELOG.md` updated under `[Unreleased]`
- Branch is up to date with `main`

---

## 5. Stage 4 — Stage

**Trigger:** Merge to `main` automatically triggers `cd-staging.yml` via `workflow_call`.

**Staging environment gates:**

| Check        | How                                           | Pass criteria                                                        |
| ------------ | --------------------------------------------- | -------------------------------------------------------------------- |
| Image build  | `docker/build-push-action`                    | Exit 0                                                               |
| Helm deploy  | `helm upgrade --wait --timeout 5m`            | All pods ready                                                       |
| Smoke tests  | `infrastructure/scripts/deploy/smoke-test.sh` | `/health` + `/ready` return 200; key API endpoint responds correctly |
| Staging soak | Manual — minimum 30 minutes observation       | No alert fires in `infrastructure/monitoring/prometheus/rules/`      |

**Exit gate:** On-call engineer confirms staging soak. Signs off in the GitHub deployment environment.

---

## 6. Stage 5 — Produce

**Trigger:** Manual `workflow_dispatch` on `cd-production.yml` with explicit version input.

**Pre-deploy checklist (enforced by `check-error-budget` job):**

- Error budget remaining ≥ 10% (`slo:error_budget_remaining:ratio{service="api-gateway"}`)
- No active P0/P1 incidents (on-call confirms)
- PRR completed for any change touching database schema, new external dependencies, or autonomy level changes

**Canary progression:**

| Stage       | Traffic | Observation window | Gate                                 |
| ----------- | ------- | ------------------ | ------------------------------------ |
| 5% canary   | 5%      | 15 min             | Error rate < 1%; p99 latency < 500ms |
| 25% canary  | 25%     | 15 min             | Same thresholds                      |
| Full deploy | 100%    | —                  | Helm rollout complete                |

**Auto-rollback:** `rollback-on-failure` job triggers on any canary gate failure — runs `rollback.sh --env production`.

**Post-deploy:**

- Confirm Golden Signals dashboard (`infrastructure/monitoring/grafana/dashboards/golden-signals.json`) is green
- Update `CHANGELOG.md` — move `[Unreleased]` to `[X.Y.Z]`
- Tag release: `git tag vX.Y.Z && git push origin vX.Y.Z`
- Create GitHub Release with changelog entries

---

## 7. Hotfix Path

For P0 production incidents only:

1. Branch from the production tag: `hotfix/SPEC-NNN-<description>`
2. Fix and unit test locally
3. Open PR — CI gates still apply (no bypasses)
4. On-call engineer approves with a comment confirming incident context
5. Merge and deploy via `cd-production.yml` — skip 5%/25% canary, deploy 100% directly
6. File RFC within 24 hours: `docs/change-management/rfc/` (Emergency RFC)
7. Postmortem within 48 hours: `docs/postmortems/`

---

## 8. Definition of Done

A change is **Done** when all of the following are true:

- [ ] All CI gates pass on `main`
- [ ] Staging smoke tests pass
- [ ] Production deployed and Golden Signals green for 30+ minutes
- [ ] `CHANGELOG.md` updated and release tagged
- [ ] ADRs updated if architectural decisions changed
- [ ] Spec updated if implementation diverged from it
- [ ] On-call runbooks updated if operational behaviour changed
