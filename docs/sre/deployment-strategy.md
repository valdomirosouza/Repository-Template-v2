# Deployment Strategy Guide

> **Status:** Active · **Version:** 1.0 · **Last updated:** 2026-05-31
> **Owner:** SRE Lead + DevOps Lead
> **Related:** `skills/change-management/deploy-rollback.md` · `docs/runbooks/rollback-procedure.md` · `docs/sre/slo/slo.yaml`

This guide answers **which deployment strategy to use and why** — not how to execute it (see `skills/change-management/deploy-rollback.md` for step-by-step procedures).

---

## 1. Strategy Decision Matrix

Use this matrix as the first step for every production deploy.

| Condition                                                    | Recommended strategy                                 |
| ------------------------------------------------------------ | ---------------------------------------------------- |
| Normal feature deploy to a stateless service                 | **Canary**                                           |
| Database migration included                                  | **Canary** with migration run before traffic shift   |
| Two incompatible API versions must coexist during transition | **Blue-Green**                                       |
| Frontend static asset deploy (no server-side state)          | **Rolling** or **Blue-Green**                        |
| Config or feature flag change only (no new binary)           | **Feature Flag** — no deploy needed                  |
| Critical hotfix — MTTR must be < 15 min                      | **Hotfix path** (§6)                                 |
| Low-risk patch to a non-critical service                     | **Rolling**                                          |
| Service with persistent WebSocket connections                | **Blue-Green** (avoids mid-flight connection drops)  |
| AI agent action type added or changed                        | **Canary** + HITL gate enforcement review (ADR-0015) |

**When in doubt: use Canary.** It is the default for all production deploys in `cd-production.yml`.

---

## 2. Canary Deploy

### When to use

- Default for all stateless API services
- Any change with non-trivial blast radius
- When you need progressive traffic validation before full rollout

### Traffic progression

```
5% → observe 15 min → 25% → observe 15 min → 100%
```

Auto-rollback triggers if either gate fails during the observation window (§5).

### Mechanics

```bash
# Helm canary weight controlled via values
helm upgrade app ./infrastructure/helm/api-gateway \
  --set canary.enabled=true \
  --set canary.weight=5 \
  --set image.tag=<version>
```

The canary pod runs alongside the stable pod. The Ingress controller splits traffic by weight. Both versions share the same database and Kafka topics — the new version **must** be backwards-compatible with the existing schema.

### Database migration rule

Run migrations **before** traffic shift, never during:

```
1. Run: uv run alembic upgrade head   # new schema applied
2. Deploy canary at 5%                # new code reads new schema
3. Keep old code running — it must tolerate new schema columns (additive only)
4. Complete canary progression to 100%
5. Remove old schema columns in a follow-up migration (separate PR)
```

Never remove or rename columns in the same deploy that introduces new code depending on them.

### Suitable change types

| Change                              | Safe for canary?                         |
| ----------------------------------- | ---------------------------------------- |
| New endpoint added                  | ✅ Yes                                   |
| Existing endpoint behaviour changed | ✅ Yes — validate at 5%                  |
| Breaking API change                 | ❌ Use Blue-Green with versioned routing |
| Additive DB column                  | ✅ Yes — migrate first                   |
| Column rename / drop                | ❌ Multi-step migration required         |
| New Kafka topic                     | ✅ Yes                                   |
| Avro schema change (additive)       | ✅ Yes                                   |
| Avro schema change (breaking)       | ❌ Coordinate with Schema Registry       |

---

## 3. Blue-Green Deploy

### When to use

- Breaking API changes where two versions must coexist temporarily
- WebSocket-heavy services (avoids connection drops during rolling/canary)
- Frontend SPA deploys where asset versioning must be atomic
- When you need instant full rollback capability (switch DNS/Ingress, not Helm rollback)

### Mechanics

```
Green (current live) ──── 100% traffic
Blue  (new version)  ──── 0% traffic  →  smoke test  →  100%  →  green decommissioned
```

```bash
# Deploy to blue slot (no traffic)
helm upgrade app-blue ./infrastructure/helm/api-gateway \
  --set image.tag=<new-version> \
  --set service.name=app-blue

# Run smoke tests against blue
bash infrastructure/scripts/deploy/smoke-test.sh --base-url http://app-blue.internal

# Switch Ingress to blue (atomic traffic cut)
kubectl patch ingress api-gateway -n production \
  --type=json \
  -p='[{"op":"replace","path":"/spec/rules/0/http/paths/0/backend/service/name","value":"app-blue"}]'

# Monitor Golden Signals for 10 minutes, then decommission green
helm uninstall app-green -n production
```

### Rollback

Switch the Ingress pointer back to the green service — sub-second, no pod restart required.

### Cost consideration

Blue-green doubles compute during the transition window (typically 10–30 minutes). Coordinate with FinOps budget for resource-intensive services (ADR-0020).

---

## 4. Rolling Deploy

### When to use

- Low-risk patch deploys to non-critical services
- Frontend static asset deploys where brief mixed-version serving is acceptable
- Internal tooling or batch job updates

### Mechanics

Kubernetes rolling update — controlled by `RollingUpdateStrategy` in `deployment.yaml`:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0 # never reduce capacity below 100%
    maxSurge: 1 # add one new pod at a time
```

Monitor rollout:

```bash
kubectl rollout status deployment/api-gateway -n production
kubectl rollout history deployment/api-gateway -n production
```

Rollback:

```bash
kubectl rollout undo deployment/api-gateway -n production
```

### When NOT to use rolling

- Services with database migrations — use canary (§2)
- Services handling long-lived connections — use blue-green (§3)
- Any P1-risk deploy — use canary for the observation window

---

## 5. SLO Gate Thresholds

All strategies share the same Golden Signals gates during observation windows. Thresholds are defined in `docs/sre/slo/slo.yaml` and enforced by `cd-production.yml`.

| Signal       | Auto-rollback threshold | Source                               |
| ------------ | ----------------------- | ------------------------------------ |
| Error rate   | > 1% over 5 min         | `http_requests_total{status=~"5.."}` |
| p99 latency  | > 500ms over 5 min      | `http_request_duration_seconds`      |
| Availability | < 99.9%                 | SLO burn rate alert                  |

**Tuning thresholds per service:** override in `infrastructure/helm/<service>/values-production.yaml`:

```yaml
canary:
  sloGates:
    errorRateThreshold: 0.005 # 0.5% for sensitive services
    p99LatencyMs: 300 # stricter latency for real-time services
    observationWindowSeconds: 900 # 15 min (default)
```

**Error budget gate:** `cd-production.yml` blocks the deploy entirely if the remaining error budget is < 10%. Check before deploying:

```bash
curl -s "$PROMETHEUS_URL/api/v1/query" \
  --data-urlencode 'query=slo:error_budget_remaining:ratio{service="api-gateway"}' \
  | jq '.data.result[0].value[1]'
# Must be > 0.10
```

---

## 6. Hotfix Deploy Path

For P1 incidents requiring MTTR < 15 minutes — skip the standard canary observation windows.

```
1. Create hotfix branch: git checkout -b hotfix/SPEC-NNN-description
2. Apply minimal fix — no refactoring, no scope creep
3. Push directly to staging for smoke test (no canary wait)
4. Deploy to production at 100% immediately (no canary steps)
5. Monitor Golden Signals manually for 10 minutes
6. File retroactive RFC within 24h (emergency-change label — CLAUDE.md §11)
7. Open post-mortem in docs/postmortems/ within 48h
```

Hotfix PRs must use `emergency-change` label and reference the incident ticket.

---

## 7. Feature Flag as Deployment Substitute

When a change only toggles behaviour without changing binaries, use a feature flag instead of a deploy — **zero deployment risk, instant rollback**.

```bash
# Enable a feature for 5% of requests (flagd OpenFeature)
kubectl apply -f infrastructure/feature-flags/flags/<flag-name>.yaml

# Gradual rollout: update flag targeting rules
# Rollback: revert flag targeting rules — no redeploy required
```

Use feature flags when:

- A/B testing new behaviour
- Gradual rollout of a new UI component
- Enabling AI agent autonomy levels (controlled by `autonomous-mode` flag — ADR-0015)
- Hiding an incomplete feature that ships with the binary

Do **not** use feature flags as a permanent architecture — they accumulate as tech debt. Each flag must have a documented removal date in `infrastructure/feature-flags/flags/<flag-name>.yaml`.

---

## 8. Risk Scoring

Before choosing a strategy, score the deploy risk:

| Factor                          | Low (0)    | Medium (1)        | High (2)             |
| ------------------------------- | ---------- | ----------------- | -------------------- |
| Change size                     | < 50 lines | 50–500 lines      | > 500 lines          |
| DB migration included           | No         | Additive only     | Destructive / rename |
| Services affected               | 1 internal | 1 external-facing | Multiple             |
| Time since last deploy          | < 1 week   | 1–4 weeks         | > 4 weeks            |
| Error budget remaining          | > 50%      | 10–50%            | < 10%                |
| Previous incidents on this path | 0          | 1                 | ≥ 2                  |

**Score interpretation:**

| Total | Recommended strategy        | Extra precautions                                     |
| ----- | --------------------------- | ----------------------------------------------------- |
| 0–3   | Rolling or Canary           | Standard observation window                           |
| 4–6   | Canary                      | Double observation window (30 min per step)           |
| 7–9   | Canary with extended window | SRE on-call notified; post-deploy monitoring 1h       |
| 10–12 | Blue-Green                  | CAB review; PRR re-run; on-call standby during deploy |

---

## 9. DORA Impact

Every deploy outcome is recorded for DORA metrics (ADR-0028):

- `dora_deployments_total{outcome="success"}` — incremented on clean 100% promotion
- `dora_deployments_total{outcome="rollback"}` — incremented on any auto or manual rollback
- `dora_lead_time_seconds` — measured from first commit to production deploy

Rollbacks drive up **Change Failure Rate**. If CFR exceeds 5% (DORA Elite threshold), a retrospective is required within 5 business days — review risk scores and strategy choices as primary inputs.
