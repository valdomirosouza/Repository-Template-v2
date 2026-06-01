# Deploy to Production

This guide walks through the complete production deployment flow — from pre-flight checks through
canary rollout to post-deploy verification. Read it before your first production deploy.

**Related resources:**

- Workflow: `.github/workflows/cd-production.yml`
- Skill: `skills/change-management/deploy-rollback.md`
- Skill: `skills/sre/prr.md`
- Skill: `skills/compliance/iso27001-change-management.md`
- Runbook: `docs/runbooks/RB-003-hitl-recovery-and-rollback.md`

---

## Step 1 — Classify the change

Every production deployment is classified before it starts. The classification determines
whether CAB approval is required and which deploy window applies.

| Classification | Description                                                      | CAB required?      | Deploy window       |
| -------------- | ---------------------------------------------------------------- | ------------------ | ------------------- |
| **Standard**   | Pre-approved, low-risk; matches an existing pre-approved pattern | No                 | Mon–Thu 10:00–17:00 |
| **Normal**     | Requires RFC approved by CAB before merge                        | Yes — before merge | Scheduled window    |
| **Emergency**  | TL + SecOps async approval; retroactive RFC within 24 h          | Yes — async        | Any time            |

**Decision rule:** if the change touches infra, auth, encryption, or a new external integration,
it is at minimum a Normal change. Bug fixes and dependency patches are typically Standard.

See `skills/compliance/iso27001-change-management.md` for the full decision tree.

---

## Step 2 — Pre-flight checklist

Complete every item before triggering the deploy pipeline.

**Production Readiness Review (PRR)**

```bash
# Confirm all PRR items are green — see skills/sre/prr.md
# Minimum: load test, runbook present, rollback tested in staging, SLO baseline set
```

**Staging gates**

- [ ] `cd-staging.yml` completed successfully for this SHA
- [ ] DAST (OWASP ZAP full scan) passed — link report in PR body
- [ ] Cosign attestation verified on the staging image
- [ ] Smoke tests green (`infrastructure/scripts/deploy/smoke-test.sh --env staging`)

**RFC reference (Normal / Emergency changes)**

Every production commit must carry an RFC_ID when the change type label is
`normal-change` or `emergency-change`:

```
# In the merge commit or PR title body:
Refs: RFC-0042
```

The `cd-production.yml` `cab-check` job validates RFC approval status before proceeding.

---

## Step 3 — Trigger the deploy

The `cd-production.yml` workflow is triggered by `workflow_dispatch` or `workflow_call`
from a release pipeline. Pass the SHA you want to deploy:

```bash
gh workflow run cd-production.yml \
  --field sha=$(git rev-parse HEAD) \
  --repo your-org/your-project
```

**What the pipeline does:**

```
cab-check        → validates RFC approval for normal/emergency changes
  ↓
build-and-sign   → docker build → trivy scan → cosign sign (keyless OIDC)
  ↓
sbom-attest      → syft generate SBOM → cosign attest to registry image
  ↓
canary-5pct      → helm upgrade --set canary.weight=5 → SLO gate (5 min)
  ↓
canary-25pct     → helm upgrade --set canary.weight=25 → SLO gate (10 min)
  ↓
canary-100pct    → helm upgrade --set canary.weight=100 (full cutover)
  ↓
smoke-test       → infrastructure/scripts/deploy/smoke-test.sh --env production
  ↓
emit-dora-event  → records dora_deployments_total metric (Prometheus)
  ↓
record-change    → appends to docs/change-log/ (deployer, RFC_ID, image digest, SBOM hash)
```

---

## Step 4 — Monitor during canary

Watch these signals during each canary window. A breach at any stage triggers automatic
rollback (`make rollback`).

```bash
# Golden Signals dashboard (Grafana)
open http://grafana.your-domain/d/golden-signals

# Live error rate
kubectl logs -l app=api-gateway -n production --tail=50 -f | jq '.level,.msg'

# SLO burn rate (Prometheus)
curl -s http://prometheus.your-domain/api/v1/query \
  --data-urlencode 'query=sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))' \
  | jq '.data.result[0].value[1]'
```

**SLO gate thresholds** (defined in `docs/sre/slo/slo.yaml`):

| Signal               | Threshold     | Action on breach              |
| -------------------- | ------------- | ----------------------------- |
| Error rate           | > 1%          | Automatic rollback            |
| p99 latency          | > 2× baseline | Page on-call, manual decision |
| Saturation (CPU/mem) | > 80%         | Page on-call, manual decision |

---

## Step 5 — Rollback procedure

If a canary window breaches an SLO gate or smoke tests fail:

```bash
# Automated rollback (triggered by pipeline SLO gate)
make rollback

# Manual rollback (on-call decision)
make rollback SERVICE=api-gateway
```

**RTO target:** < 1 hour (p50), per `dora_mttr_target_seconds: 3600` in `docs/sre/slo/slo.yaml`.

The rollback reverts the Helm release to the previous revision:

```bash
helm rollback api-gateway -n production
```

After rollback, open an incident in PagerDuty and follow `docs/runbooks/RB-003-hitl-recovery-and-rollback.md`.
For Emergency changes, file the retroactive RFC within 24 hours and conduct a postmortem within 5 business days.

---

## Step 6 — Post-deploy

After a successful full-traffic cutover:

**Record the deployment** (automated by pipeline, verify manually if needed):

```bash
# docs/change-log/<date>-<service>.md should exist with:
# deployer, RFC_ID, image digest (SHA-256), SBOM hash, timestamp
ls docs/change-log/
```

**DORA metric** (emitted automatically by `emit-dora-event` job):

```bash
# Verify counter incremented
curl -s http://prometheus.your-domain/api/v1/query \
  --data-urlencode 'query=dora_deployments_total{service="api-gateway",result="success"}' \
  | jq '.data.result[0].value[1]'
```

**Update on-call handoff** in `docs/sre/on-call-schedule.md` if this deploy changes
an SLO threshold or introduces new alert rules.

---

## Quick reference

```bash
# Classify change
# → see skills/compliance/iso27001-change-management.md

# Run PRR
# → see skills/sre/prr.md

# Trigger deploy
gh workflow run cd-production.yml --field sha=<SHA>

# Monitor
open http://grafana.your-domain/d/golden-signals

# Rollback
make rollback

# Check DORA
make agent-feedback-check   # queries Prometheus for HITL bias state + DORA counters
```
