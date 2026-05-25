# Skill — Deploy & Rollback

**Owner:** DevOps Lead | **Reviewer:** SRE Lead | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill for any deploy or rollback operation.

---

## Running a Deploy

Script: `infrastructure/scripts/deploy/deploy.sh`

```bash
bash infrastructure/scripts/deploy/deploy.sh \
  --strategy canary \
  --env production \
  --version 1.2.3 \
  --service app
```

| Parameter    | Values                            | Notes                                   |
| ------------ | --------------------------------- | --------------------------------------- |
| `--strategy` | `canary`, `blue-green`, `rolling` | Default: canary for production          |
| `--env`      | `staging`, `production`           | Sets Kubernetes namespace               |
| `--version`  | SemVer string                     | Must match a pushed container image tag |
| `--service`  | Helm release name                 | Default: `app`                          |

Pre-deploy checklist before running:

- [ ] PRR complete and all blocking items checked
- [ ] RFC approved by CAB (Normal changes)
- [ ] Error budget > 10% (checked automatically by script)
- [ ] Staging smoke tests passed

---

## Canary Deploy Steps and Monitoring

The canary strategy promotes traffic in three steps: **5% → 25% → 100%**.

At each step the script:

1. Deploys the new version to the specified weight
2. Waits **15 minutes** (configurable via `CANARY_WAIT_SECONDS`)
3. Queries Prometheus for error rate and p99 latency
4. If either exceeds the SLO threshold — auto-rollback is triggered

Golden Signals gate thresholds:

- Error rate: `> 1%` → fail
- p99 latency: `> 500ms` → fail

Monitor the deploy live on the Golden Signals dashboard:
`infrastructure/monitoring/grafana/dashboards/golden-signals.json`

---

## Triggering a Manual Rollback

Script: `infrastructure/scripts/deploy/rollback.sh`

```bash
# Roll back to the previous Helm revision (auto-detected)
bash infrastructure/scripts/deploy/rollback.sh --env production

# Roll back to a specific Helm revision
bash infrastructure/scripts/deploy/rollback.sh --env production --revision 5
```

The script:

1. Finds the last successful Helm revision (or uses `--revision`)
2. Executes `helm rollback` with `--wait`
3. Runs smoke tests post-rollback
4. Monitors Golden Signals for 10 minutes
5. Exits non-zero if service is still degraded after rollback

---

## Verifying Rollback Success

Script: `infrastructure/scripts/deploy/smoke-test.sh`

```bash
bash infrastructure/scripts/deploy/smoke-test.sh \
  --env production \
  --base-url https://api.example.com
```

Checks performed:

- `GET /health` → 200 with `{"status":"ok"}`
- `GET /ready` → 200
- `GET /v1/status` → 200 with non-empty body
- `GET /v1/hitl/status` → 200 (HITL gateway connectivity)
- `GET /metrics` → 200 with Prometheus data

Each check retries up to 3 times with 5s backoff. Output is a JSON summary of all checks.

---

## When to Escalate from Automated to Manual Rollback

Escalate if:

- Automated rollback script exits non-zero (smoke tests still failing after rollback)
- The previous Helm revision is also broken (regression in earlier version)
- Database schema migration is involved (Helm rollback alone is insufficient)
- The issue is infrastructure-level (Kafka, Redis, Kubernetes) — Helm rollback won't help

For database rollbacks: see `docs/runbooks/disaster-recovery.md` Scenario 2.

---

## Post-Rollback Checklist

After any production rollback (automated or manual):

- [ ] Open a P2 (or P1 if SLO breached) incident in the incident channel
- [ ] Notify stakeholders: Engineering Manager, Product Owner (within 15 min)
- [ ] Update the status page
- [ ] Identify the broken version and prevent it from being re-deployed
- [ ] Schedule post-mortem within 5 business days
- [ ] Document timeline in `docs/postmortems/YYYY-MM-DD-<incident-name>.md`
- [ ] Update CHANGELOG.md with the revert entry
