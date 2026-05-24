# Runbook — Rollback Procedure

**Runbook ID:** RB-001
**Severity:** P1–P2
**Owner:** SRE Lead
**Last reviewed:** 2026-05-24

---

## When to Rollback

### Automatic Triggers (handled by `rollback.sh`)

- Error rate exceeds SLO threshold for > 2 minutes
- p99 latency exceeds SLO target for > 2 minutes
- Availability drops below SLO target

### Manual Triggers

- On-call engineer determines the deploy is the root cause
- CAB instructs rollback
- Security incident linked to the current deploy

---

## Symptoms

- `CriticalErrorRate` or `HighP99Latency` alert firing after a recent deploy
- Golden Signals dashboard showing degradation correlated with deploy time
- User reports of errors starting after a deploy

---

## Automated Rollback

The deploy script (`deploy.sh`) triggers `rollback.sh` automatically if Golden
Signals checks fail during canary promotion.

To trigger manually:

```bash
bash infrastructure/scripts/deploy/rollback.sh \
  --env=production \
  --service=<service-name>
```

This runs:

1. `helm history <release>` — identifies last successful revision
2. `helm rollback <release> <revision> --wait` — rolls back Helm release
3. `smoke-test.sh` — verifies rollback restored service health
4. 10-minute Golden Signals monitoring window

---

## Manual Rollback Procedure

Use this when automated rollback fails or is insufficient.

### Step 1 — Identify the target revision

```bash
helm history <release-name> -n <namespace> --max 10
```

Find the last revision with status `deployed` before the bad deploy.

### Step 2 — Execute rollback

```bash
helm rollback <release-name> <revision-number> \
  --namespace <namespace> \
  --wait \
  --timeout 5m
```

### Step 3 — Verify rollback

```bash
# Check pod status
kubectl get pods -n <namespace> -l app=<service-name>

# Run smoke tests
bash infrastructure/scripts/deploy/smoke-test.sh \
  --env=production \
  --base-url=https://<service-endpoint>
```

### Step 4 — Monitor Golden Signals

Open Grafana dashboard and monitor for 10 minutes:

- Error rate returning to baseline (< 1%)
- p99 latency returning to baseline (< 500ms)
- Pod availability ≥ 2 healthy pods

---

## Database Rollback

If the deploy included a database migration:

```bash
# Identify current migration version
uv run alembic current

# Rollback one migration
uv run alembic downgrade -1

# Rollback to a specific version
uv run alembic downgrade <revision-id>
```

⚠️ Test migration rollback in staging before executing in production.

---

## Feature Flag Rollback

If the issue is isolated to a feature controlled by a feature flag:

```bash
# Disable the feature flag (no deploy required)
# Update flags/autonomous-mode.yaml or equivalent
kubectl apply -f infrastructure/feature-flags/flags/<flag-name>.yaml
```

This is the fastest rollback option when applicable.

---

## Post-Rollback Actions

- [ ] Confirm Golden Signals are green for 10 minutes post-rollback
- [ ] Open incident: record rollback time, revision rolled back to, trigger reason
- [ ] Notify stakeholders: status page update if user-facing impact occurred
- [ ] Schedule post-mortem within 48 hours (P1) or 5 business days (P2)
- [ ] Block re-deploy of the rolled-back version until root cause is identified

---

## Escalation

| Situation                 | Escalation                                 |
| ------------------------- | ------------------------------------------ |
| Automated rollback fails  | Page SRE Lead immediately                  |
| Manual rollback fails     | Page Tech Lead + SRE Lead                  |
| Data corruption suspected | Page Tech Lead + DPO + Engineering Manager |
| Security incident         | Page Security Lead + Engineering Manager   |
