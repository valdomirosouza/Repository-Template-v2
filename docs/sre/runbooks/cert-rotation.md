# Runbook: TLS Certificate Rotation

**Owner:** SRE Lead | **Reviewer:** Security Lead | **Last updated:** 2026-05-28

---

## Overview

This runbook covers three certificate rotation scenarios:

| Scenario                                           | Trigger                                          | Urgency                 |
| -------------------------------------------------- | ------------------------------------------------ | ----------------------- |
| [Routine renewal](#1-routine-renewal-cert-manager) | cert-manager auto-renews at 2/3 of lifetime      | Automated — verify only |
| [Manual rotation](#2-manual-rotation)              | Forced rotation after incident or key compromise | P1 — act within 4 h     |
| [Emergency revocation](#3-emergency-revocation)    | Private key confirmed compromised                | P0 — act within 1 h     |

---

## Alert thresholds

| Alert                       | Threshold           | Action                              |
| --------------------------- | ------------------- | ----------------------------------- |
| `CertificateExpiryWarning`  | < 30 days remaining | Verify auto-renewal is running      |
| `CertificateExpiryCritical` | < 7 days remaining  | Trigger manual rotation immediately |
| `CertificateExpired`        | 0 days remaining    | Emergency revocation + reissue      |

Alerts are defined in `infrastructure/monitoring/prometheus/alert-rules.yaml`.

---

## 1. Routine Renewal (cert-manager)

cert-manager renews certificates automatically at 2/3 of the certificate lifetime
(~60 days for a 90-day Let's Encrypt cert). No manual action is normally required.

### Verify auto-renewal is healthy

```bash
# Check certificate status
kubectl get certificates -n default

# Inspect a specific certificate
kubectl describe certificate agent-service-tls -n default

# Check cert-manager controller logs for errors
kubectl logs -n cert-manager deploy/cert-manager | grep -i "error\|fail" | tail -30

# Check ACME challenge is resolving
kubectl get challenges -n default
```

Expected output: `READY=True`, `STATUS=Certificate is up to date`.

### If auto-renewal is stuck

```bash
# Force renewal by deleting the current certificate secret
# cert-manager will recreate it automatically
kubectl delete secret agent-service-tls -n default

# Watch cert-manager issue the new certificate
kubectl get certificate agent-service-tls -n default -w
```

---

## 2. Manual Rotation

Use this procedure when forced rotation is required (e.g. after a security incident
where key material may have been exposed, but no confirmed compromise).

### Step 1 — Issue a new certificate

```bash
# Option A: Let cert-manager reissue (preferred)
kubectl annotate certificate agent-service-tls \
  cert-manager.io/issue-temporary-certificate="true" \
  --overwrite -n default

# Option B: Manual Let's Encrypt via certbot (if cert-manager is unavailable)
certbot certonly --standalone -d <your-domain> \
  --preferred-challenges http-01
```

### Step 2 — Update the Kubernetes Secret

```bash
# If using certbot output:
kubectl create secret tls agent-service-tls \
  --cert=/etc/letsencrypt/live/<your-domain>/fullchain.pem \
  --key=/etc/letsencrypt/live/<your-domain>/privkey.pem \
  -n default \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Step 3 — Reload the Ingress

```bash
# nginx-ingress reads the updated Secret automatically via a watch.
# Verify the new cert is live:
echo | openssl s_client -connect <your-domain>:443 2>/dev/null \
  | openssl x509 -noout -dates -subject
```

### Step 4 — Verify no downtime

```bash
# Check Golden Signals for the next 5 minutes
kubectl top pods -n default
# Confirm error rate stays below SLO threshold
```

---

## 3. Emergency Revocation

Use when the private key is **confirmed compromised** — e.g. it appeared in a
public repository, was recovered from a decommissioned disk, or was accessed by
an unauthorised party.

**SLA: complete within 1 hour of confirmation.**

### Step 1 — Revoke immediately

```bash
# Revoke via certbot (requires the original account key)
certbot revoke \
  --cert-path /etc/letsencrypt/live/<your-domain>/cert.pem \
  --reason keyCompromise

# Or via ACME API directly if certbot is unavailable:
# Use acme.sh or the Let's Encrypt API with reason=keyCompromise
```

### Step 2 — Delete the compromised Secret

```bash
kubectl delete secret agent-service-tls -n default
```

### Step 3 — Reissue immediately

Follow [Step 1–4 of Manual Rotation](#step-1--issue-a-new-certificate) above.

### Step 4 — Rotate dependent secrets

If the compromised key was also used for mTLS (service-to-service), rotate all
service certificates in the mesh:

```bash
# List all Certificate resources
kubectl get certificates -A

# Delete and reissue each one
kubectl delete certificate <name> -n <namespace>
```

### Step 5 — Notify and document

1. File a postmortem in `docs/postmortems/` within 24 hours.
2. Notify the Security Lead and DPO within 1 hour of revocation.
3. If EU or Brazilian residents' data may have been exposed during the window,
   notify the DPO for GDPR/LGPD breach assessment — 72-hour notification clock starts.

---

## 4. Application Encryption Key Rotation (DB_ENCRYPTION_KEY)

This is distinct from TLS certificates but included here for completeness.

**Rotation schedule:** 180 days (ADR-0008, ADR-0018).

```bash
# Step 1: Generate new key
NEW_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Step 2: Add DB_ENCRYPTION_KEY_V2 to Vault alongside existing key
vault kv put secret/app/db-encryption-key \
  value="<existing-key>" \
  value_v2="$NEW_KEY"

# Step 3: Deploy app version that reads both keys (decrypt v1/v2, encrypt with v2)
# The enc:v2: wire format is used by the new version.
# This is a planned enhancement — see ADR-0018 §3.4 for the rotation design.

# Step 4: Run re-encryption job
make db-reencrypt

# Step 5: Remove old key from Vault
vault kv patch secret/app/db-encryption-key -delete=value
```

---

## 5. Escalation

| Condition                          | Escalate to            | Timeline                       |
| ---------------------------------- | ---------------------- | ------------------------------ |
| cert-manager stuck > 2 h           | SRE Lead + DevOps Lead | Immediately                    |
| Certificate expired (site down)    | SRE Lead + Tech Lead   | P0 — page immediately          |
| Key compromise confirmed           | Security Lead + DPO    | Within 1 h                     |
| GDPR/LGPD breach assessment needed | DPO + Legal            | Within 1 h of DPO notification |
