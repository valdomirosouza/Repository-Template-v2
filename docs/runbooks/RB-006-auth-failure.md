# Runbook — Authentication / JWT Validation Failure

**Runbook ID:** RB-006
**Severity:** P1–P2
**Owner:** Security Lead
**Last reviewed:** 2026-05-31
**Reviewed by:** Tech Lead

---

## Symptoms

- Alert: `AuthFailureRateHigh` firing — 401/403 error rate > 5% over 5 minutes
- All authenticated API endpoints returning `401 Unauthorized` or `403 Forbidden`
- Logs contain: `JWT validation failed`, `token expired`, `invalid signature`, or `JWKS fetch error`
- Grafana: spike in `http_requests_total{status="401"}` or `http_requests_total{status="403"}`
- Users unable to log in or perform any authenticated actions

---

## Impact

- **Who is affected:** all authenticated users and service-to-service calls
- **Severity:** P1 if total auth failure (no user can authenticate); P2 if partial (specific token types or services affected)
- **SLO at risk:** `api-gateway` availability SLO (target ≥ 99.9%); `api-gateway` error rate SLO (target ≥ 99.5%)
- **Security note:** auth failures may indicate an active attack — involve Security Lead immediately if attack pattern suspected

---

## Immediate Mitigation

1. **Check if the auth middleware is misconfigured** (most common cause after a deploy):
   ```bash
   kubectl logs -n production -l app=api-gateway --tail=200 \
     | grep -E "JWT|auth|401|403|JWKS|signature"
   ```
2. **Check JWKS endpoint reachability** — if the IDP is unreachable, token validation fails:
   ```bash
   kubectl exec -n production deploy/api-gateway -- \
     curl -sf "$JWT_JWKS_URL" | jq '.keys | length'
   ```
3. **Roll back the last deploy** if auth breakage correlates with a recent deployment:
   ```bash
   bash infrastructure/scripts/deploy/rollback.sh --env production
   ```
4. **If brute-force attack suspected** — enable rate limiting at ingress level:
   ```bash
   kubectl annotate ingress api-gateway -n production \
     nginx.ingress.kubernetes.io/limit-rps="10" --overwrite
   ```

---

## Root Cause Investigation

```bash
# Check auth error distribution — is it all users or specific tokens?
kubectl logs -n production -l app=api-gateway --tail=500 \
  | grep -E "JWT|401|403" | sort | uniq -c | sort -rn | head -20

# Check IDP / JWKS endpoint health
curl -sf "$JWT_JWKS_URL"
curl -sf "$JWT_ISSUER_URL/.well-known/openid-configuration"

# Check token expiry settings in config
kubectl get configmap api-gateway-config -n production -o yaml \
  | grep -E "JWT|TOKEN|EXPIRY|ISSUER"

# Check for clock skew between services (common JWT validation failure cause)
kubectl exec -n production deploy/api-gateway -- date -u
kubectl exec -n production deploy/postgresql -- date -u

# Check Redis for refresh token store health (A07 — single-use enforcement)
kubectl exec -n production deploy/redis -- \
  redis-cli ping

# Check recent certificate/key rotation events
kubectl get events -n production --sort-by=.lastTimestamp \
  | grep -i "secret\|cert\|key\|rotation" | tail -20
```

Key questions:

- Did a recent deploy change `JWT_SECRET`, `JWT_ISSUER`, or `JWT_ALGORITHM` settings?
- Was a key rotation performed recently? Was the new key propagated to all services?
- Is the JWKS endpoint reachable? Is the IDP itself healthy?
- Is clock skew > 60 seconds between services (causes `nbf`/`exp` validation failures)?
- Is the error limited to a specific token type (access vs refresh) or all tokens?
- Are there signs of token stuffing or brute-force (high volume from single IP)?

---

## Resolution

### Case A — JWKS endpoint unreachable (IDP down)

```bash
# Check IDP pod / external service status
kubectl get pods -n production -l app=identity-provider

# If IDP is a managed service, check provider status page
# Temporary mitigation: cache last-known JWKS in ConfigMap
kubectl create configmap jwks-cache \
  --from-literal=keys="$(curl -sf $JWT_JWKS_URL)" \
  -n production --dry-run=client -o yaml | kubectl apply -f -
```

### Case B — Key rotation not propagated

```bash
# Update JWT_SECRET or JWKS reference in all affected deployments
kubectl set env deployment/api-gateway JWT_SECRET="<new-secret>" -n production
kubectl rollout status deployment/api-gateway -n production

# Verify new tokens validate correctly
curl -X POST https://api/v1/auth/token -d '{"username":"test","password":"test"}' \
  | jq '.access_token' | jwt decode -
```

### Case C — Clock skew

```bash
# Force NTP sync on affected nodes
kubectl debug node/<node-name> -it --image=busybox -- \
  chronyc makestep

# Increase JWT leeway in config (temporary — fix clock properly)
kubectl set env deployment/api-gateway JWT_LEEWAY_SECONDS="30" -n production
```

### Case D — Config error introduced by deploy

```bash
# Roll back to previous deployment
helm rollback api-gateway -n production --wait

# Verify auth is restored
curl -sf https://api/health/auth | jq .
```

---

## Post-Incident

- [ ] Observe 401/403 error rate return to baseline (< 0.1%) for 10 minutes
- [ ] Audit all failed authentication events during the outage window — check `audit_log` for anomalies
- [ ] If attack suspected: rotate affected secrets immediately; notify Security Lead and DPO
- [ ] Check for any PII exposure in error responses (OWASP A09 — logging failures)
- [ ] If P1: open post-mortem in `docs/postmortems/` within 48 hours
- [ ] Review brute-force protection thresholds (account lockout after 5 failed attempts per CLAUDE.md §3.2)
- [ ] Update this runbook with any new findings

---

## Prevention

- Automate JWKS caching with a TTL so IDP downtime does not immediately break auth
- Add pre-deploy smoke test for auth endpoint (`/health/auth`) in `cd-staging.yml`
- Alert on clock skew > 30 seconds between service pods
- Enforce key rotation runbook (`docs/runbooks/secret-rotation.md`) with staged rollout — propagate new key before retiring old one
- Monitor `http_requests_total{status="401"}` with a tight alerting threshold (5% over 5 min)

---

## Escalation

| Situation                                       | Escalation                                                            |
| ----------------------------------------------- | --------------------------------------------------------------------- |
| Total auth loss > 15 min                        | Page Engineering Manager + Security Lead                              |
| Active brute-force / credential stuffing attack | Page Security Lead immediately; consider blocking at WAF              |
| Token or key compromise confirmed               | Page Security Lead + DPO + Engineering Manager — incident severity P1 |
| PII exposed in error responses                  | Page DPO immediately                                                  |
