# Change Management Process

**Owner:** Tech Lead + SRE Lead | **Last reviewed:** 2026-05-24
**Reference:** MONOREPO-STRUCTURE-EN.md Section 1

---

## Change Types

| Type          | Trigger                                                                        | RFC required                     | CAB approval      | Timeline                          |
| ------------- | ------------------------------------------------------------------------------ | -------------------------------- | ----------------- | --------------------------------- |
| **Standard**  | Minor enhancement, bug fix, docs                                               | No                               | No                | Normal PR process                 |
| **Normal**    | Architecture change, API contract change, new PII processing, guardrail change | Yes                              | Yes (weekly CAB)  | Submit RFC 48h before CAB         |
| **Emergency** | Critical production fix that cannot wait                                       | Yes (async, within 24h post-fix) | TL + SecOps async | Immediate; post-mortem within 48h |

---

## Step 1 — Issue Creation

Open a GitHub Issue using `.github/ISSUE_TEMPLATE/change_request.md`.

Required fields:

- Problem description and motivation
- Referenced spec (`specs/*`)
- Change type: Standard / Normal / Emergency
- Estimated impact (affected services, data flows, users)
- Acceptance criteria (Given / When / Then)
- Rollback plan
- Privacy impact (Y/N — if Y, DPIA/RIPD review required)

---

## Step 2 — RFC (Normal and Emergency changes)

File `docs/change-management/rfc/RFC-NNNN-<title>.md` using `RFC-TEMPLATE.md`.

| Change type   | Reviewer                  | Approver          | Timeline               |
| ------------- | ------------------------- | ----------------- | ---------------------- |
| Normal        | Tech Lead + Security Lead | CAB               | 48h before CAB meeting |
| Emergency     | Tech Lead (async)         | TL + SecOps async | Within 4h              |
| PII-affecting | DPO review mandatory      | DPO + CAB         | Add 24h for DPO review |

---

## Step 3 — Branch and PR

Branch naming:

```
feature/SPEC-NNN-<description>
fix/SPEC-NNN-<description>
hotfix/SPEC-NNN-<description>
```

Open PR using `.github/pull_request_template.md`. Required fields:

- Linked Issue number
- Referenced spec path
- Impacted ADRs
- Deploy command
- Rollback plan
- Privacy impact checkbox

---

## Step 4 — CI/CD Pipeline Gates

All gates must pass before merge. See `.github/workflows/ci.yml` for full pipeline.

| Gate             | Criterion                       | Blocks            |
| ---------------- | ------------------------------- | ----------------- |
| Lint             | Zero critical violations        | Merge             |
| Unit tests       | Coverage ≥ 80%, zero failures   | Merge             |
| SAST             | Zero CRITICAL/HIGH findings     | Merge             |
| Secret detection | Zero secrets detected           | Merge             |
| Container scan   | Zero Critical CVEs              | Merge             |
| PII scan         | No real PII in fixtures or logs | Merge             |
| Human review     | Minimum 1 approved reviewer     | Merge             |
| Error budget     | Budget > 10%                    | Production deploy |
| RFC approved     | For Normal / Emergency changes  | Production deploy |

---

## Step 5 — Deploy Script

```bash
bash infrastructure/scripts/deploy/deploy.sh \
  --strategy=canary \
  --env=production \
  --service=<service-name> \
  --version=<version>
```

Deploy steps (canary):

1. Pre-deploy health check — verify current pods healthy
2. Deploy 5% canary weight
3. Smoke tests (`smoke-test.sh`)
4. 15-minute Golden Signals monitoring window
5. Promote to 25% → repeat monitoring → promote to 100%
6. Auto-rollback if SLO thresholds breached at any step

---

## Step 6 — Post-Deploy Tests

- **Smoke tests:** `infrastructure/scripts/deploy/smoke-test.sh`
- **Golden Signals check:** Traffic, Error rate, Saturation, Latency — all green for 5 min
- **CUJ validation:** Monitor all critical user journey dashboards for 5 min
- **Privacy check:** Confirm no PII appearing in new log paths (automated grep)

---

## Step 7 — Rollback Procedure

**Automatic triggers:**

- Error rate exceeds SLO threshold (defined in `docs/sre/slo/slo.yaml`)
- p99 latency exceeds SLO target for > 2 minutes
- Availability drops below SLO target

**Manual rollback:**

```bash
bash infrastructure/scripts/deploy/rollback.sh --env=production --service=<name>
```

Full procedure: `docs/runbooks/rollback-procedure.md`

---

## Step 8 — Changelog Update

Update `CHANGELOG.md` under `[Unreleased]` with the change:

```markdown
### Added / Changed / Fixed / Security / Privacy

- <Description>. (Issue #NNN, ADR-NNNN, RFC-NNNN)
```

Categories: `Added` | `Changed` | `Fixed` | `Security` | `Removed` | `Privacy`

---

## Step 9 — Post-Deploy Monitoring Windows

| Change type               | Monitoring window                     | Sign-off required  |
| ------------------------- | ------------------------------------- | ------------------ |
| Standard                  | 24 hours                              | On-call engineer   |
| Infrastructure            | 72 hours                              | SRE Lead           |
| PII pipeline change       | 24 hours + DPO sign-off               | DPO                |
| AI agent behaviour change | 48 hours + HITL rejection rate review | AI Governance Lead |
